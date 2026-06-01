"""
A2binder affinity prediction calculator.

Integrates A2binder model from PALM project for predicting antibody-antigen binding affinity.
"""

from typing import Dict, Any, List, Optional
import logging
import numpy as np
from pathlib import Path
import sys

from ..design import Design
from ..config import MetricConfig
from ..utils.pdb_utils import get_sequence_from_pdb

logger = logging.getLogger(__name__)


class A2binderCalculator:
    """
    Calculate binding affinity using A2binder model.
    
    A2binder is a fine-tuned BERT model for predicting antibody-antigen binding affinity.
    It requires heavy chain, light chain, and antigen sequences.
    """
    
    def __init__(
        self,
        model_path: str,
        heavy_model_dir: str,
        light_model_dir: str,
        antibody_tokenizer_dir: str,
        antibody_vocab_dir: Optional[str] = None,
        tokenizer_name: str = "common",
        token_length_list: str = "2,3",
        heavy_max_len: int = 140,
        light_max_len: int = 140,
        antigen_max_len: int = 300,
        device: str = "cuda",
        use_light_chain: bool = True,
        model_type: str = "BERTBinding_AbDab_cnn",
        nanobody_model: bool = False,
    ):
        """
        Initialize A2binder calculator.
        
        Args:
            model_path: Path to A2binder model checkpoint (.pth file)
                For nanobody models, use the model from Zenodo: https://zenodo.org/records/17090473
            heavy_model_dir: Path to pre-trained HeavyRoformer model directory
            light_model_dir: Path to pre-trained LightRoformer model directory
            antibody_tokenizer_dir: Path to antibody tokenizer directory
            antibody_vocab_dir: Path to antibody vocabulary file (optional)
            tokenizer_name: Tokenizer name (default: "common")
            token_length_list: Token length list for tokenizer (default: "2,3")
            heavy_max_len: Maximum length for heavy chain (default: 140)
            light_max_len: Maximum length for light chain (default: 140)
            antigen_max_len: Maximum length for antigen (default: 300)
            device: Device to run model on (default: "cuda")
            use_light_chain: Whether to use light chain (for nanobodies, set to False)
            model_type: Model architecture type (default: "BERTBinding_AbDab_cnn")
            nanobody_model: Whether using nanobody-specific model from Zenodo (default: False)
                If True, the model was fine-tuned on nanobody/sdAb data
        """
        self.model_path = model_path
        self.heavy_model_dir = heavy_model_dir
        self.light_model_dir = light_model_dir
        self.antibody_tokenizer_dir = antibody_tokenizer_dir
        self.antibody_vocab_dir = antibody_vocab_dir
        self.tokenizer_name = tokenizer_name
        self.token_length_list = token_length_list
        self.heavy_max_len = heavy_max_len
        self.light_max_len = light_max_len
        self.antigen_max_len = antigen_max_len
        self.device = device
        self.use_light_chain = use_light_chain
        self.model_type = model_type
        self.nanobody_model = nanobody_model
        
        # Auto-detect nanobody model if use_light_chain is False
        if not use_light_chain and not nanobody_model:
            logger.info("use_light_chain=False detected. Consider using nanobody-specific model from Zenodo for better accuracy.")
        
        # Lazy loading - models will be loaded on first use
        self._model = None
        self._heavy_tokenizer = None
        self._light_tokenizer = None
        self._antigen_tokenizer = None
        self._heavy_tokenizer_obj = None
        self._light_tokenizer_obj = None
        self._torch = None  # Lazy import torch
        
    def _load_model(self):
        """Lazy load A2binder model and tokenizers."""
        if self._model is not None:
            return
        
        # Lazy import torch to avoid requiring it when not using A2binder
        if self._torch is None:
            try:
                import torch
                self._torch = torch
            except ImportError:
                raise ImportError(
                    "torch is required for A2binder calculator. "
                    "Please install it with: pip install torch"
                )
        
        torch = self._torch  # Use cached torch module
        
        try:
            # Try to find PALM code directory
            # Check common locations
            palm_code_dir = None
            possible_paths = [
                Path(__file__).parent.parent.parent.parent.parent / "PALM-main" / "Code",
                Path(self.model_path).parent.parent.parent.parent / "Code",  # Relative to model path
                Path(self.heavy_model_dir).parent.parent.parent / "Code",  # Relative to heavy model
            ]
            
            for path in possible_paths:
                if path.exists() and (path / "bert_data_prepare").exists():
                    palm_code_dir = path
                    break
            
            if palm_code_dir and palm_code_dir.exists():
                sys.path.insert(0, str(palm_code_dir))
            
            # Import PALM modules
            from bert_data_prepare.tokenizer import get_tokenizer
            from transformers import AutoTokenizer
            import model.bert_binding as module_arch
            
            # Load tokenizers
            logger.info("Loading A2binder tokenizers...")
            
            # Determine vocab directory
            if self.antibody_vocab_dir:
                vocab_dir = self.antibody_vocab_dir
            elif palm_code_dir:
                vocab_dir = str(palm_code_dir / "ProcessedData" / "vocab" / "heavy-2-3.csv")
            else:
                raise ValueError("Cannot determine antibody vocabulary directory. Please provide antibody_vocab_dir.")
            
            # Heavy chain tokenizer
            self._heavy_tokenizer_obj = get_tokenizer(
                tokenizer_name=self.tokenizer_name,
                add_hyphen=False,
                logger=logger,
                vocab_dir=vocab_dir,
                token_length_list=self.token_length_list
            )
            self._heavy_tokenizer = self._heavy_tokenizer_obj.get_bert_tokenizer(
                max_len=self.heavy_max_len,
                tokenizer_dir=self.antibody_tokenizer_dir
            )
            
            # Light chain tokenizer (same as heavy for now)
            self._light_tokenizer_obj = get_tokenizer(
                tokenizer_name=self.tokenizer_name,
                add_hyphen=False,
                logger=logger,
                vocab_dir=vocab_dir,
                token_length_list=self.token_length_list
            )
            self._light_tokenizer = self._light_tokenizer_obj.get_bert_tokenizer(
                max_len=self.light_max_len,
                tokenizer_dir=self.antibody_tokenizer_dir
            )
            
            # Antigen tokenizer (ESM2)
            esm_dir = 'facebook/esm2_t30_150M_UR50D'
            esm_cache_dir = None
            if palm_code_dir:
                esm_cache_path = palm_code_dir / "esm2" / "esm2_150m"
                if esm_cache_path.exists():
                    esm_cache_dir = str(esm_cache_path)
            
            self._antigen_tokenizer = AutoTokenizer.from_pretrained(
                esm_dir,
                cache_dir=esm_cache_dir,
                max_length=self.antigen_max_len
            )
            
            # Load model
            logger.info(f"Loading A2binder model from {self.model_path}...")
            if self.nanobody_model:
                logger.info("Using nanobody-specific model (fine-tuned on nanobody/sdAb data)")
            
            model_config = {
                "type": self.model_type,
                "args": {
                    "heavy_dir": self.heavy_model_dir,
                    "light_dir": self.light_model_dir,
                    "antigen_dir": esm_dir,
                    "emb_dim": 256
                }
            }
            
            # Create model instance
            model_class = getattr(module_arch, model_config["type"])
            self._model = model_class(**model_config["args"])
            
            # Load checkpoint
            # Check if model_path is a .pth checkpoint file or a directory
            model_path_obj = Path(self.model_path)
            if model_path_obj.is_file() and model_path_obj.suffix == '.pth':
                # Load from checkpoint file (e.g., model_best.pth from Zenodo)
                logger.info(f"Loading checkpoint from file: {self.model_path}")
                checkpoint = torch.load(self.model_path, map_location=self.device)
                if 'state_dict' in checkpoint:
                    state_dict = checkpoint['state_dict']
                else:
                    state_dict = checkpoint
                self._model.load_state_dict(state_dict)
            elif model_path_obj.is_dir():
                # Load from directory containing separate model components
                # This is for models saved as separate components (heavymodel, lightmodel, antigenmodel)
                logger.info(f"Loading model components from directory: {self.model_path}")
                # For directory-based loading, we would need to reconstruct the model
                # For now, we'll try to find a checkpoint file in the directory
                checkpoint_files = list(model_path_obj.glob("*.pth"))
                if checkpoint_files:
                    checkpoint_path = checkpoint_files[0]
                    logger.info(f"Found checkpoint file: {checkpoint_path}")
                    checkpoint = torch.load(checkpoint_path, map_location=self.device)
                    if 'state_dict' in checkpoint:
                        state_dict = checkpoint['state_dict']
                    else:
                        state_dict = checkpoint
                    self._model.load_state_dict(state_dict)
                else:
                    raise FileNotFoundError(
                        f"No checkpoint file (.pth) found in directory: {self.model_path}. "
                        f"Please provide the path to model_best.pth file."
                    )
            else:
                raise FileNotFoundError(
                    f"Model path not found: {self.model_path}. "
                    f"Please provide a valid path to model_best.pth file or model directory."
                )
            
            self._model.to(self.device)
            self._model.eval()
            
            logger.info("A2binder model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading A2binder model: {e}")
            raise RuntimeError(f"Failed to load A2binder model: {e}")
    
    def _tokenize_sequence(self, sequence: str, tokenizer, split_func, max_len: int) -> Dict[str, Any]:
        """
        Tokenize a sequence using the tokenizer.
        
        Args:
            sequence: Amino acid sequence
            tokenizer: Tokenizer instance
            split_func: Function to split sequence into tokens
            max_len: Maximum sequence length
            
        Returns:
            Dictionary of tokenized inputs
        """
        # Split sequence into tokens
        tokens = split_func(sequence)
        # Insert whitespace between tokens
        tokenized_seq = " ".join(tokens)
        
        # Tokenize
        tokenized = tokenizer(
            tokenized_seq,
            padding="max_length",
            max_length=max_len,
            truncation=True,
            return_tensors="pt"
        )
        
        # Remove batch dimension for single sequence
        return {k: v.squeeze(0) for k, v in tokenized.items()}
    
    def _predict_affinity(
        self,
        heavy_seq: str,
        light_seq: str,
        antigen_seq: str
    ) -> float:
        """
        Predict binding affinity using A2binder model.
        
        Args:
            heavy_seq: Heavy chain sequence
            light_seq: Light chain sequence
            antigen_seq: Antigen sequence
            
        Returns:
            Predicted affinity score (higher = better binding)
        """
        self._load_model()
        
        # Tokenize sequences
        heavy_tokens = self._tokenize_sequence(
            heavy_seq,
            self._heavy_tokenizer,
            self._heavy_tokenizer_obj.split,
            self.heavy_max_len
        )
        
        light_tokens = self._tokenize_sequence(
            light_seq,
            self._light_tokenizer,
            self._light_tokenizer_obj.split,
            self.light_max_len
        )
        
        # Antigen tokenization (no splitting needed for ESM2)
        antigen_tokens = self._antigen_tokenizer(
            antigen_seq,
            padding="max_length",
            max_length=self.antigen_max_len,
            truncation=True,
            return_tensors="pt"
        )
        antigen_tokens = {k: v.squeeze(0) for k, v in antigen_tokens.items()}
        
        # Move to device
        heavy_tokens = {k: v.to(self.device) for k, v in heavy_tokens.items()}
        light_tokens = {k: v.to(self.device) for k, v in light_tokens.items()}
        antigen_tokens = {k: v.to(self.device) for k, v in antigen_tokens.items()}
        
        # Add batch dimension
        heavy_tokens = {k: v.unsqueeze(0) for k, v in heavy_tokens.items()}
        light_tokens = {k: v.unsqueeze(0) for k, v in light_tokens.items()}
        antigen_tokens = {k: v.unsqueeze(0) for k, v in antigen_tokens.items()}
        
        # Predict (torch is already imported in _load_model)
        import torch
        with torch.no_grad():
            output = self._model(heavy_tokens, light_tokens, antigen_tokens)
            # Apply sigmoid for probability (if needed)
            affinity_score = torch.sigmoid(output).cpu().item()
        
        return float(affinity_score)
    
    def calculate(self, pdb_path: str, design: Design) -> Dict[str, Any]:
        """
        Calculate A2binder affinity prediction.
        
        Args:
            pdb_path: Path to PDB structure file
            design: Design object containing sequences and metadata
            
        Returns:
            Dictionary with affinity prediction metrics
        """
        try:
            # Extract sequences from PDB or use design sequences
            chains = get_sequence_from_pdb(pdb_path)
            
            # Get heavy chain sequence
            if design.binder_chain in chains:
                heavy_seq = chains[design.binder_chain]
            elif design.sequence:
                heavy_seq = design.sequence
            else:
                logger.warning("Could not find heavy chain sequence")
                return {"a2binder_affinity": 0.0}
            
            # Get light chain sequence
            if self.use_light_chain:
                # Try to find light chain in metadata
                if design.metadata and "light_chain" in design.metadata:
                    light_seq = design.metadata["light_chain"]
                elif design.metadata and "light_sequence" in design.metadata:
                    light_seq = design.metadata["light_sequence"]
                else:
                    logger.warning("use_light_chain=True but no light chain found in metadata. Using empty string.")
                    light_seq = ""
            else:
                # For nanobodies/VNAR, use empty string
                # Note: If using nanobody-specific model from Zenodo, this is the correct approach
                light_seq = ""
                if self.nanobody_model:
                    logger.debug("Using nanobody model with empty light chain")
            
            # Get antigen/target sequence
            target_chains = design.target_chain.split(",") if isinstance(design.target_chain, str) else [design.target_chain]
            antigen_seqs = []
            for chain_id in target_chains:
                if chain_id in chains:
                    antigen_seqs.append(chains[chain_id])
                elif design.target_sequence:
                    if isinstance(design.target_sequence, list):
                        antigen_seqs.extend(design.target_sequence)
                    else:
                        antigen_seqs.append(design.target_sequence)
            
            if not antigen_seqs:
                logger.warning("Could not find antigen sequence")
                return {"a2binder_affinity": 0.0}
            
            # Use first antigen sequence (or concatenate if multiple)
            antigen_seq = antigen_seqs[0] if len(antigen_seqs) == 1 else "".join(antigen_seqs)
            
            # Predict affinity
            affinity_score = self._predict_affinity(heavy_seq, light_seq, antigen_seq)
            
            return {
                "a2binder_affinity": affinity_score,
            }
            
        except Exception as e:
            logger.error(f"Error calculating A2binder affinity: {e}")
            return {"a2binder_affinity": 0.0}
    
    def get_metric_names(self) -> List[str]:
        """Return list of metric names this calculator produces."""
        return ["a2binder_affinity"]

