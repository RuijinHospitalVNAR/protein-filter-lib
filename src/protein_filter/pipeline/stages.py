"""
Concrete pipeline stage implementations.

Provides ready-to-use stages for the three-stage AF3 analysis pipeline:
- Stage 1: AF3 Score Filtering (AF3ScoreFilteringStage)
- Stage 2: Foldseek Coarse Clustering (FoldseekClusteringStage)  
- Stage 3: Fine Contact-based Clustering (FineContactClusteringStage)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import json
import os
import shutil
import tempfile
import subprocess
import numpy as np
from functools import partial
from multiprocessing import Pool

from .base import (
    PipelineStage,
    PipelineData,
    StageResult,
    StructureMetrics,
    ClusterInfo,
    PerformanceMetrics,
)
from .config import Stage1Config, Stage2Config, Stage3Config

logger = logging.getLogger(__name__)


# ============================================================================
# Stage 1: AF3 Score Filtering
# ============================================================================

def _extract_metrics_worker(cif_file: str, pdb_dir: str, compute_ipsae: bool = True) -> tuple:
    """
    Worker function to extract metrics from a single structure.
    
    This is a module-level function to enable multiprocessing.
    """
    try:
        from pathlib import Path
        import numpy as np
        
        from protein_filter.utils.af3_utils import extract_metrics_from_af3_output
        from protein_filter.utils.pdb_utils import calculate_clash_score
        from protein_filter.utils.pdockq_utils import get_pdockq, pdb_2_coords, _is_cif_file
        
        metrics = {}
        cif_path = Path(cif_file)
        
        # Extract pLDDT from CIF B-factor
        is_cif = _is_cif_file(str(cif_path))
        try:
            chain_coords, plddt_array = pdb_2_coords(str(cif_path), is_cif=is_cif)
            if len(plddt_array) > 0:
                plddt_normalized = plddt_array / 100.0
                metrics['plddt'] = float(np.mean(plddt_normalized))
        except Exception as e:
            logger.debug(f"Failed to extract pLDDT from {cif_path}: {e}")
            metrics['plddt'] = 0.0
        
        # Calculate clashes
        try:
            clashes = calculate_clash_score(str(cif_path), threshold=2.4, only_ca=False)
            metrics['clashes'] = clashes
        except Exception as e:
            logger.debug(f"Failed to calculate clashes for {cif_path}: {e}")
            metrics['clashes'] = 999
        
        # Find JSON files for metrics extraction
        # Priority: confidences.json (full PAE) > summary_confidences.json
        json_for_ipsae = []
        json_for_metrics = []
        
        # Same directory
        json_for_ipsae.extend(list(cif_path.parent.glob("confidences.json")))
        json_for_ipsae.extend(list(cif_path.parent.glob("*_confidences.json")))
        json_for_ipsae.extend(list(cif_path.parent.glob("*_data.json")))
        json_for_metrics.extend(list(cif_path.parent.glob("summary_confidences.json")))
        json_for_metrics.extend(list(cif_path.parent.glob("*_summary_confidences.json")))
        
        # Parent directory (for seed-*/model.cif format)
        parent_dir = cif_path.parent.parent
        if parent_dir.exists() and parent_dir != cif_path.parent:
            json_for_ipsae.extend(list(parent_dir.glob("*_confidences.json")))
            json_for_ipsae.extend(list(parent_dir.glob("*_data.json")))
            json_for_metrics.extend(list(parent_dir.glob("*_summary_confidences.json")))
        
        json_path_for_ipsae = None
        
        # Extract basic metrics
        all_json = json_for_ipsae + json_for_metrics
        if all_json:
            try:
                metrics_json = json_for_metrics[0] if json_for_metrics else all_json[0]
                json_dir = metrics_json.parent
                json_metrics = extract_metrics_from_af3_output(str(json_dir))
                metrics.update(json_metrics)
            except Exception as e:
                logger.debug(f"Failed to parse JSON: {e}")
        
        # Find JSON with PAE matrix for ipSAE
        if json_for_ipsae:
            for candidate in json_for_ipsae:
                if 'summary' not in candidate.name.lower():
                    json_path_for_ipsae = str(candidate)
                    break
        
        # Calculate ranking_confidence
        if 'iptm' in metrics and 'ptm' in metrics:
            metrics['ranking_confidence'] = 0.8 * metrics['iptm'] + 0.2 * metrics['ptm']
        elif 'iptm' in metrics:
            metrics['ranking_confidence'] = metrics['iptm']
        
        # Calculate ipSAE if requested
        if compute_ipsae and 'ipsae' not in metrics and json_path_for_ipsae:
            try:
                from protein_filter.utils.ipsae_utils import calculate_ipsae_from_script
                ipsae_metrics = calculate_ipsae_from_script(
                    json_path=json_path_for_ipsae,
                    pdb_path=str(cif_path),
                    pae_cutoff=5.0,
                    dist_cutoff=5.0,
                )
                if ipsae_metrics.get("ipsae") is not None:
                    metrics["ipsae"] = float(ipsae_metrics["ipsae"])
                    if "ipsae_d0chn" in ipsae_metrics:
                        metrics["ipsae_d0chn"] = float(ipsae_metrics["ipsae_d0chn"])
                    if "ipsae_d0dom" in ipsae_metrics:
                        metrics["ipsae_d0dom"] = float(ipsae_metrics["ipsae_d0dom"])
            except Exception as e:
                logger.debug(f"Failed to calculate ipSAE for {cif_path}: {e}")
        
        # Calculate pDockQ
        try:
            pdockq = get_pdockq(str(cif_path))
            metrics['pdockq'] = pdockq
        except Exception as e:
            logger.debug(f"Failed to calculate pDockQ for {cif_path}: {e}")
            metrics['pdockq'] = 0.0
        
        # Get relative path
        pdb_path = Path(pdb_dir)
        rel_path = cif_path.relative_to(pdb_path)
        
        return str(rel_path), metrics
    except Exception as e:
        logger.warning(f"Failed to process {cif_file}: {e}")
        return None, None


class AF3ScoreFilteringStage(PipelineStage):
    """
    Stage 1: Filter structures based on AF3 prediction quality scores.
    
    Filters by: pLDDT, clashes, pDockQ, iPTM, ranking_confidence, ipSAE
    """
    
    def __init__(self, config: Stage1Config):
        super().__init__(config.to_dict())
        self.stage_config = config
    
    @property
    def name(self) -> str:
        return "stage1_af3_filtering"
    
    def process(self, data: PipelineData) -> StageResult:
        """Execute AF3 score filtering."""
        pdb_dir = data.pdb_dir
        if not pdb_dir or not pdb_dir.exists():
            return StageResult(
                success=False,
                data=data,
                error_message=f"PDB directory not found: {pdb_dir}"
            )
        
        # Find all CIF files
        cif_files = sorted(list(pdb_dir.rglob("*.cif")))
        self._logger.info(f"Found {len(cif_files)} CIF files")
        
        if len(cif_files) == 0:
            return StageResult(
                success=False,
                data=data,
                error_message="No CIF files found"
            )
        
        # Extract metrics in parallel
        max_workers = min(self.stage_config.n_jobs, 8)
        self._logger.info(f"Extracting metrics with {max_workers} workers...")
        
        worker_func = partial(
            _extract_metrics_worker,
            pdb_dir=str(pdb_dir),
            compute_ipsae=self.stage_config.compute_ipsae
        )
        
        metrics_dict = {}
        with Pool(processes=max_workers) as pool:
            results = pool.map(worker_func, [str(f) for f in cif_files])
        
        for rel_path, metrics in results:
            if rel_path and metrics:
                metrics_dict[rel_path] = metrics
                data.all_structure_metrics[rel_path] = StructureMetrics(
                    file_path=rel_path,
                    plddt=metrics.get('plddt'),
                    iptm=metrics.get('iptm'),
                    ptm=metrics.get('ptm'),
                    ipsae=metrics.get('ipsae'),
                    pdockq=metrics.get('pdockq'),
                    clashes=metrics.get('clashes'),
                    ranking_confidence=metrics.get('ranking_confidence'),
                    raw_metrics=metrics,
                )
        
        self._logger.info(f"Extracted metrics from {len(metrics_dict)} structures")
        
        # Apply filters
        cfg = self.stage_config
        filtered_files = []
        filter_stats = {
            'total': len(metrics_dict),
            'failed_plddt': 0,
            'failed_clashes': 0,
            'failed_pdockq': 0,
            'failed_iptm': 0,
            'failed_ranking_confidence': 0,
            'failed_ipsae': 0,
            'passed': 0
        }
        
        for file_name, metrics in metrics_dict.items():
            passed = True
            
            if metrics.get('plddt', 0.0) < cfg.plddt_threshold:
                filter_stats['failed_plddt'] += 1
                passed = False
                continue
            
            if metrics.get('clashes', 999) >= cfg.clashes_threshold:
                filter_stats['failed_clashes'] += 1
                passed = False
                continue
            
            if metrics.get('pdockq', 0.0) < cfg.pdockq_threshold:
                filter_stats['failed_pdockq'] += 1
                passed = False
                continue
            
            if metrics.get('iptm', 0.0) < cfg.iptm_threshold:
                filter_stats['failed_iptm'] += 1
                passed = False
                continue
            
            ranking_conf = metrics.get('ranking_confidence')
            if ranking_conf is not None and ranking_conf < cfg.ranking_confidence_threshold:
                filter_stats['failed_ranking_confidence'] += 1
                passed = False
                continue
            
            # ipSAE filter (higher = better interface confidence)
            ipsae = metrics.get('ipsae')
            if ipsae is not None and ipsae < cfg.ipsae_threshold:
                filter_stats['failed_ipsae'] += 1
                passed = False
                continue
            
            if passed:
                filtered_files.append(file_name)
                filter_stats['passed'] += 1
        
        # Update data
        data.filtered_files = filtered_files
        data.filter_stats = filter_stats
        data.stage = self.name
        
        # Log results
        pass_rate = (filter_stats['passed'] / filter_stats['total'] * 100) if filter_stats['total'] > 0 else 0
        self._logger.info(f"Filtering: {len(filtered_files)}/{len(metrics_dict)} passed ({pass_rate:.2f}%)")
        self._logger.info(f"Filter thresholds: pLDDT>={cfg.plddt_threshold}, clashes<{cfg.clashes_threshold}, "
                         f"pDockQ>={cfg.pdockq_threshold}, iPTM>={cfg.iptm_threshold}, ipSAE>={cfg.ipsae_threshold}")
        
        # Log metrics distribution for passed structures
        if filtered_files:
            passed_metrics = [metrics_dict[f] for f in filtered_files]
            for metric_name in ['plddt', 'iptm', 'ipsae', 'pdockq', 'clashes']:
                values = [m.get(metric_name) for m in passed_metrics if m.get(metric_name) is not None]
                if values:
                    self._logger.info(f"  {metric_name}: {np.mean(values):.3f} ± {np.std(values):.3f} (n={len(values)})")
        
        return StageResult(
            success=len(filtered_files) > 0,
            data=data,
            error_message=None if filtered_files else "No structures passed filtering"
        )


# ============================================================================
# Stage 2: Foldseek Coarse Clustering
# ============================================================================

class FoldseekClusteringStage(PipelineStage):
    """
    Stage 2: Coarse clustering using Foldseek structure similarity.
    """
    
    def __init__(self, config: Stage2Config):
        super().__init__(config.to_dict())
        self.stage_config = config
    
    @property
    def name(self) -> str:
        return "stage2_foldseek_clustering"
    
    def process(self, data: PipelineData) -> StageResult:
        """Execute Foldseek coarse clustering."""
        if self.stage_config.skip_foldseek:
            self._logger.info("Skipping Foldseek (--skip-foldseek)")
            # Treat all filtered files as one cluster
            data.coarse_clusters = {
                0: ClusterInfo(
                    cluster_id=0,
                    file_names=data.filtered_files.copy(),
                    method="skip_foldseek"
                )
            }
            data.stage = self.name
            return StageResult(success=True, data=data)
        
        pdb_dir = data.pdb_dir
        filtered_files = data.filtered_files
        
        if not filtered_files:
            return StageResult(
                success=False,
                data=data,
                error_message="No filtered files to cluster"
            )
        
        self._logger.info(f"Clustering {len(filtered_files)} structures with Foldseek...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create symlinks
            structures_dir = temp_path / "structures"
            structures_dir.mkdir(parents=True, exist_ok=True)
            index_to_file = []
            
            for i, file_name in enumerate(filtered_files):
                full_path = pdb_dir / file_name
                if not full_path.exists():
                    continue
                link_path = structures_dir / f"{i:06d}.cif"
                try:
                    link_path.symlink_to(full_path.resolve())
                    index_to_file.append(file_name)
                except OSError as e:
                    self._logger.warning(f"Failed to create symlink: {e}")
            
            if not index_to_file:
                return StageResult(
                    success=False,
                    data=data,
                    error_message="No valid structure files"
                )
            
            # Create Foldseek database
            database_path = temp_path / "structures_db"
            cfg = self.stage_config
            
            try:
                cmd = [cfg.foldseek_path, "createdb", str(structures_dir), str(database_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    self._logger.error(f"Foldseek createdb failed: {result.stderr[:500]}")
                    return StageResult(success=False, data=data, error_message="Foldseek createdb failed")
            except Exception as e:
                self._logger.error(f"Foldseek createdb error: {e}")
                return StageResult(success=False, data=data, error_message=str(e))
            
            # Run clustering
            cluster_db_path = temp_path / "clusters_db"
            try:
                cmd = [
                    cfg.foldseek_path, 'cluster',
                    str(database_path),
                    str(cluster_db_path),
                    str(temp_path / "tmp"),
                    '-s', str(cfg.sensitivity),
                    '-c', str(cfg.coverage),
                    '--min-seq-id', str(cfg.min_seq_id),
                    '--threads', str(cfg.n_jobs)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if result.returncode != 0:
                    self._logger.error(f"Foldseek cluster failed: {result.stderr[:500]}")
                    return StageResult(success=False, data=data, error_message="Foldseek cluster failed")
            except Exception as e:
                self._logger.error(f"Foldseek cluster error: {e}")
                return StageResult(success=False, data=data, error_message=str(e))
            
            # Convert to TSV
            cluster_tsv_path = temp_path / "clusters.tsv"
            try:
                cmd_tsv = [
                    cfg.foldseek_path, 'createtsv',
                    str(database_path),
                    str(database_path),
                    str(cluster_db_path),
                    str(cluster_tsv_path)
                ]
                result_tsv = subprocess.run(cmd_tsv, capture_output=True, text=True, timeout=300)
                if result_tsv.returncode != 0 or not cluster_tsv_path.exists():
                    self._logger.warning("Foldseek createtsv failed")
                    # Fall back to single cluster
                    data.coarse_clusters = {
                        0: ClusterInfo(cluster_id=0, file_names=filtered_files, method="foldseek_fallback")
                    }
                    data.stage = self.name
                    return StageResult(success=True, data=data)
            except Exception as e:
                self._logger.warning(f"Foldseek createtsv error: {e}")
                data.coarse_clusters = {
                    0: ClusterInfo(cluster_id=0, file_names=filtered_files, method="foldseek_fallback")
                }
                data.stage = self.name
                return StageResult(success=True, data=data)
            
            # Parse clustering results
            n_indexed = len(index_to_file)
            
            def parse_foldseek_id(member: str) -> Optional[int]:
                s = member.strip()
                if not s:
                    return None
                if '_' in s:
                    s = s.split('_')[0].strip()
                try:
                    idx = int(s)
                    return idx if 0 <= idx < n_indexed else None
                except ValueError:
                    return None
            
            def idx_to_fname(member: str) -> Optional[str]:
                idx = parse_foldseek_id(member)
                if idx is not None:
                    return index_to_file[idx]
                return None
            
            rep_to_members: Dict[str, List[str]] = {}
            with open(cluster_tsv_path, 'r') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        rep, mem = parts[0], parts[1]
                        rep_to_members.setdefault(rep, []).append(mem)
            
            # Convert to clusters
            coarse_clusters = {}
            if rep_to_members:
                struct_set_to_files: Dict[frozenset, List[str]] = {}
                for rep, mems in rep_to_members.items():
                    cluster_files = []
                    seen = set()
                    for m in [rep] + mems:
                        fname = idx_to_fname(m)
                        if fname and fname not in seen:
                            seen.add(fname)
                            cluster_files.append(fname)
                    if cluster_files:
                        key = frozenset(cluster_files)
                        if key not in struct_set_to_files:
                            struct_set_to_files[key] = list(cluster_files)
                
                for cid, (key, files) in enumerate(struct_set_to_files.items()):
                    coarse_clusters[cid] = ClusterInfo(
                        cluster_id=cid,
                        file_names=list(dict.fromkeys(files)),
                        method="foldseek"
                    )
            
            if not coarse_clusters:
                coarse_clusters = {
                    0: ClusterInfo(cluster_id=0, file_names=filtered_files, method="foldseek_single")
                }
            
            data.coarse_clusters = coarse_clusters
            data.stage = self.name
            
            self._logger.info(f"Foldseek clustering: {len(coarse_clusters)} clusters")
            
            return StageResult(success=True, data=data)


# ============================================================================
# Stage 3: Fine Contact-based Clustering
# ============================================================================

class FineContactClusteringStage(PipelineStage):
    """
    Stage 3: Fine clustering within coarse clusters based on H-A contacts.
    """
    
    def __init__(self, config: Stage3Config):
        super().__init__(config.to_dict())
        self.stage_config = config
    
    @property
    def name(self) -> str:
        return "stage3_fine_clustering"
    
    def process(self, data: PipelineData) -> StageResult:
        """Execute fine contact-based clustering."""
        from protein_filter.clustering.backend.analyzer import AF3ClusterAnalyzer
        
        pdb_dir = data.pdb_dir
        coarse_clusters = data.coarse_clusters
        cfg = self.stage_config
        
        if not coarse_clusters:
            return StageResult(
                success=False,
                data=data,
                error_message="No coarse clusters to refine"
            )
        
        all_fine_labels = []
        all_file_names = []
        fine_clusters = {}
        
        sorted_coarse = sorted(coarse_clusters.items(), key=lambda x: x[1].size, reverse=True)
        
        for coarse_id, cluster_info in sorted_coarse:
            cluster_files = cluster_info.file_names
            cluster_size = len(cluster_files)
            
            self._logger.info(f"Processing coarse cluster {coarse_id} ({cluster_size} structures)")
            
            if cluster_size < cfg.min_cluster_size_for_fine:
                self._logger.info(f"  Cluster too small, skipping fine clustering")
                fine_labels = [coarse_id] * cluster_size
                all_fine_labels.extend(fine_labels)
                all_file_names.extend(cluster_files)
                
                fine_clusters[coarse_id] = ClusterInfo(
                    cluster_id=coarse_id,
                    file_names=cluster_files,
                    method="coarse_only"
                )
                continue
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create symlinks
                for i, file_name in enumerate(cluster_files):
                    source_file = pdb_dir / file_name
                    link_name = temp_path / f"struct_{i:06d}.cif"
                    if source_file.exists():
                        link_name.symlink_to(source_file.resolve())
                
                try:
                    analyzer = AF3ClusterAnalyzer(
                        pdb_dir=str(temp_path),
                        chainA=data.chain_a,
                        antigen_chains=data.antigen_chains,
                        contact_cutoff=cfg.contact_cutoff,
                        irmsd_cutoff=5.0,
                        n_jobs=cfg.n_jobs,
                        contact_mode='jaccard',
                        contact_atom_type='interface'
                    )
                    analyzer.interface_cutoff = cfg.interface_cutoff
                    analyzer.interface_method = 'residue'
                    
                    ok = analyzer.load_and_process_data()
                    if not ok or len(analyzer.contact_sets) == 0:
                        self._logger.warning(f"  Failed to load contacts, using coarse labels")
                        fine_labels = [coarse_id] * cluster_size
                        all_fine_labels.extend(fine_labels)
                        all_file_names.extend(cluster_files)
                        fine_clusters[coarse_id] = ClusterInfo(
                            cluster_id=coarse_id,
                            file_names=cluster_files,
                            method="load_failed"
                        )
                        continue
                    
                    fine_n_clusters = max(2, min(cfg.max_fine_clusters, cluster_size // 3))
                    
                    analyzer.perform_coarse_clustering(
                        method=cfg.clustering_method,
                        distance_metric='jaccard',
                        n_clusters=fine_n_clusters if cfg.clustering_method == 'kmeans' else None,
                        use_foldseek_prescreening=False,
                        max_neighbors=min(50, cluster_size - 1)
                    )
                    
                    if analyzer.coarse_labels is None:
                        fine_labels = [coarse_id] * cluster_size
                    else:
                        base_fine_id = coarse_id * 1000
                        fine_labels = [
                            base_fine_id + label if label >= 0 else -1
                            for label in analyzer.coarse_labels
                        ]
                    
                    all_fine_labels.extend(fine_labels)
                    all_file_names.extend(cluster_files)
                    
                    n_fine = len(set(l for l in fine_labels if l >= 0))
                    self._logger.info(f"  Fine clustering: {n_fine} clusters")
                    
                    # Create fine cluster info
                    for label in set(fine_labels):
                        if label >= 0:
                            files_in_cluster = [
                                cluster_files[i] for i, l in enumerate(fine_labels) if l == label
                            ]
                            fine_clusters[label] = ClusterInfo(
                                cluster_id=label,
                                file_names=files_in_cluster,
                                method=cfg.clustering_method
                            )
                    
                except Exception as e:
                    self._logger.error(f"  Fine clustering failed: {e}")
                    fine_labels = [coarse_id] * cluster_size
                    all_fine_labels.extend(fine_labels)
                    all_file_names.extend(cluster_files)
                    fine_clusters[coarse_id] = ClusterInfo(
                        cluster_id=coarse_id,
                        file_names=cluster_files,
                        method="error"
                    )
        
        data.fine_clusters = fine_clusters
        data.fine_labels = np.array(all_fine_labels)
        data.stage = self.name
        
        n_total_fine = len(set(l for l in all_fine_labels if l >= 0))
        self._logger.info(f"Total fine clusters: {n_total_fine}")
        
        # Export clusters if requested
        if cfg.export_clusters and data.metadata.get('output_dir'):
            self._export_clusters(
                pdb_dir=pdb_dir,
                output_dir=Path(data.metadata['output_dir']),
                fine_labels=all_fine_labels,
                file_names=all_file_names
            )
        
        return StageResult(success=True, data=data)
    
    def _export_clusters(
        self,
        pdb_dir: Path,
        output_dir: Path,
        fine_labels: List[int],
        file_names: List[str]
    ) -> None:
        """Export clustered structures to directories."""
        clusters_root = output_dir / "fine_clusters"
        clusters_root.mkdir(parents=True, exist_ok=True)
        
        cluster_to_files: Dict[int, List[str]] = {}
        for label, fname in zip(fine_labels, file_names):
            cluster_to_files.setdefault(int(label), []).append(fname)
        
        # Write cluster info
        info_path = clusters_root / "cluster_info.tsv"
        with open(info_path, "w") as f:
            f.write("cluster_id\tn_structures\n")
            for cid in sorted(cluster_to_files.keys()):
                f.write(f"{cid}\t{len(cluster_to_files[cid])}\n")
        
        # Create cluster directories and symlinks
        for cid, files in cluster_to_files.items():
            if cid < 0:
                subdir = clusters_root / "noise_cluster"
            else:
                subdir = clusters_root / f"cluster_{cid}"
            subdir.mkdir(parents=True, exist_ok=True)
            
            for rel_name in files:
                src = pdb_dir / rel_name
                if not src.exists():
                    continue
                
                dst = subdir / Path(rel_name).name
                if dst.exists():
                    stem, suffix = dst.stem, dst.suffix
                    counter = 1
                    while dst.exists():
                        dst = subdir / f"{stem}_{counter}{suffix}"
                        counter += 1
                
                try:
                    abs_src = src.resolve()
                    os.symlink(abs_src, dst)
                except OSError:
                    try:
                        shutil.copy2(src, dst)
                    except Exception as copy_err:
                        self._logger.warning(
                            "复制失败，已跳过 %s -> %s: %s", src, dst, copy_err
                        )
        
        self._logger.info(f"Exported clusters to: {clusters_root}")
