"""
抗原-抗体互作位置聚类分析模块

在stage1阶段筛选符合目的结合界面的结构，基于接触集的Jaccard距离进行粗聚类。
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

# 导入聚类分析器后端
try:
    from protein_filter.clustering.backend.analyzer import AF3ClusterAnalyzer
    CLUSTERING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Failed to import clustering backend: {e}")
    CLUSTERING_AVAILABLE = False
    AF3ClusterAnalyzer = None


class InterfaceClusteringFilter:
    """抗原-抗体互作位置聚类筛选器，基于接触集的Jaccard距离进行粗聚类"""
    
    def __init__(
        self,
        pdb_dir: str,
        chainA: str = 'A',
        antigen_chains: List[str] = None,
        contact_cutoff: float = 5.0,
        interface_cutoff: float = 8.0,
        clustering_method: str = 'hdbscan',
        min_cluster_size: int = 5,
        min_samples: int = 3,
        target_cluster_id: Optional[int] = None,
        n_jobs: int = -1,
    ):
        """
        参数:
        - pdb_dir: PDB文件目录
        - chainA: 抗体/受体链ID
        - antigen_chains: 抗原链ID列表
        - contact_cutoff: 接触距离阈值（Å）
        - interface_cutoff: 界面原子识别距离阈值（Å）
        - clustering_method: 聚类方法 ('hdbscan', 'kmeans', 'dbscan')
        - min_cluster_size: 最小簇大小（HDBSCAN，0表示自动估计）
        - min_samples: 最小样本数（HDBSCAN/DBSCAN，0表示自动估计）
        - target_cluster_id: 目标簇ID（None表示选择最大的簇）
        - n_jobs: 并行处理线程数（-1=自动检测）
        """
        if not CLUSTERING_AVAILABLE:
            raise RuntimeError(
                "Clustering backend is not available. "
                "Please ensure clustering backend module exists and dependencies are installed."
            )
        
        self.pdb_dir = Path(pdb_dir)
        self.chainA = chainA
        self.antigen_chains = antigen_chains if antigen_chains else ['B']
        self.contact_cutoff = contact_cutoff
        self.interface_cutoff = interface_cutoff
        self.clustering_method = clustering_method
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.target_cluster_id = target_cluster_id
        self.n_jobs = n_jobs
        
        self.analyzer = AF3ClusterAnalyzer(
            pdb_dir=str(self.pdb_dir),
            chainA=self.chainA,
            antigen_chains=self.antigen_chains,
            contact_cutoff=self.contact_cutoff,
            irmsd_cutoff=5.0,
            n_jobs=self.n_jobs,
            residue_ranges=None,
            contact_mode='jaccard',
            contact_atom_type='interface'
        )
        self.analyzer.interface_cutoff = self.interface_cutoff
        self.analyzer.interface_method = 'residue'
        
        self.cluster_labels = None
        self.selected_file_names = []
        
    def perform_clustering(self) -> Dict[str, Any]:
        """执行聚类分析，返回包含聚类结果的字典"""
        logger.info("Starting interface clustering analysis...")
        logger.info(f"PDB directory: {self.pdb_dir}")
        logger.info(f"Chain configuration: chainA={self.chainA}, antigen_chains={self.antigen_chains}")
        
        # 加载和处理数据
        ok = self.analyzer.load_and_process_data()
        if not ok:
            raise RuntimeError("Failed to load and process structure data")
        
        if len(self.analyzer.file_names) < 2:
            if len(self.analyzer.file_names) == 1:
                self.selected_file_names = self.analyzer.file_names
                return {
                    'n_structures': 1,
                    'n_clusters': 1,
                    'selected_cluster': 0,
                    'selected_files': self.selected_file_names
                }
            raise RuntimeError("No valid structures found")
        
        logger.info(f"Loaded {len(self.analyzer.file_names)} structures")
        
        # 执行粗聚类
        logger.info(f"Performing coarse clustering with method: {self.clustering_method}")
        
        if self.clustering_method == 'hdbscan':
            try:
                import hdbscan
            except ImportError:
                logger.warning("hdbscan不可用，改用kmeans")
                self.clustering_method = 'kmeans'
            
            if self.clustering_method == 'hdbscan':
                n_samples = len(self.analyzer.file_names)
                auto_min_cluster_size, auto_min_samples = self.analyzer._auto_hdbscan_params(n_samples)
                min_cluster_size = self.min_cluster_size if self.min_cluster_size > 0 else auto_min_cluster_size
                min_samples = self.min_samples if self.min_samples > 0 else auto_min_samples
                
                logger.info(f"HDBSCAN参数: min_cluster_size={min_cluster_size}, min_samples={min_samples}")
                self.analyzer.perform_coarse_clustering(
                    method='hdbscan',
                    distance_metric='jaccard',
                    min_cluster_size=min_cluster_size,
                    min_samples=min_samples
                )
        elif self.clustering_method == 'kmeans':
            n_clusters = max(2, min(10, len(self.analyzer.file_names) // 10))
            logger.info(f"KMeans参数: n_clusters={n_clusters}")
            self.analyzer.perform_coarse_clustering(
                method='kmeans',
                distance_metric='jaccard',
                n_clusters=n_clusters
            )
        elif self.clustering_method == 'dbscan':
            if hasattr(self.analyzer, 'jaccard_distance_matrix'):
                D = self.analyzer.jaccard_distance_matrix(self.analyzer.contact_sets)
            else:
                from scipy.spatial.distance import pdist, squareform
                all_contacts = sorted(set().union(*self.analyzer.contact_sets))
                binary_features = np.array([[1 if c in cs else 0 for c in all_contacts] 
                                           for cs in self.analyzer.contact_sets])
                D = squareform(pdist(binary_features, metric='jaccard'))
            
            eps, min_samples = self.analyzer._auto_dbscan_params(D)
            logger.info(f"DBSCAN参数: eps={eps}, min_samples={min_samples}")
            self.analyzer.perform_coarse_clustering(
                method='dbscan',
                distance_metric='jaccard',
                eps=eps,
                min_samples=min_samples
            )
        else:
            raise ValueError(f"Unknown clustering method: {self.clustering_method}")
        
        self.cluster_labels = self.analyzer.coarse_labels
        
        unique_labels = set(self.cluster_labels)
        cluster_sizes = {label: np.sum(self.cluster_labels == label) for label in unique_labels}
        logger.info(f"聚类完成，发现{len(unique_labels)}个簇: {cluster_sizes}")
        
        if self.target_cluster_id is not None:
            selected_cluster = self.target_cluster_id
            if selected_cluster not in unique_labels:
                logger.warning(f"目标簇{selected_cluster}不存在，选择最大簇")
                selected_cluster = max(cluster_sizes.items(), key=lambda x: x[1])[0]
        else:
            valid_clusters = {k: v for k, v in cluster_sizes.items() if k != -1}
            selected_cluster = max(valid_clusters.items(), key=lambda x: x[1])[0] if valid_clusters else None
            if not selected_cluster:
                logger.warning("未找到有效簇，选择所有结构")
        
        if selected_cluster is not None:
            selected_indices = np.where(self.cluster_labels == selected_cluster)[0]
            self.selected_file_names = [self.analyzer.file_names[i] for i in selected_indices]
        else:
            self.selected_file_names = self.analyzer.file_names
        
        logger.info(f"选择簇{selected_cluster}，包含{len(self.selected_file_names)}个结构")
        
        return {
            'n_structures': len(self.analyzer.file_names),
            'n_clusters': len(unique_labels),
            'cluster_sizes': cluster_sizes,
            'selected_cluster': selected_cluster,
            'selected_files': self.selected_file_names,
            'cluster_labels': self.cluster_labels.tolist() if self.cluster_labels is not None else None
        }
    
    def filter_files(self, file_list: Optional[List[str]] = None) -> List[str]:
        """根据聚类结果筛选文件"""
        if not self.selected_file_names:
            if file_list is None:
                pdb_files = list(self.pdb_dir.glob("*.pdb"))
                cif_files = list(self.pdb_dir.glob("*.cif"))
                return [f.name for f in (pdb_files + cif_files)]
            return file_list
        
        if file_list is not None:
            selected_set = set(self.selected_file_names)
            return [f for f in file_list if Path(f).name in selected_set]
        
        return self.selected_file_names


def filter_by_clustering(
    pdb_dir: str,
    output_dir: Optional[str] = None,
    chainA: str = 'A',
    antigen_chains: List[str] = None,
    contact_cutoff: float = 5.0,
    interface_cutoff: float = 8.0,
    clustering_method: str = 'hdbscan',
    min_cluster_size: int = 5,
    min_samples: int = 3,
    target_cluster_id: Optional[int] = None,
    n_jobs: int = -1,
) -> Dict[str, Any]:
    """执行聚类筛选，返回包含聚类结果和筛选文件列表的字典"""
    if not CLUSTERING_AVAILABLE:
        logger.warning("聚类模块不可用，跳过聚类筛选")
        pdb_dir_path = Path(pdb_dir)
        all_files = [f.name for f in pdb_dir_path.glob("*.pdb") + list(pdb_dir_path.glob("*.cif"))]
        return {
            'clustering_enabled': False,
            'selected_files': all_files,
            'n_selected': len(all_files)
        }
    
    filter_obj = InterfaceClusteringFilter(
        pdb_dir=pdb_dir,
        chainA=chainA,
        antigen_chains=antigen_chains,
        contact_cutoff=contact_cutoff,
        interface_cutoff=interface_cutoff,
        clustering_method=clustering_method,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        target_cluster_id=target_cluster_id,
        n_jobs=n_jobs,
    )
    
    clustering_results = filter_obj.perform_clustering()
    
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        selected_files_path = output_path / "clustering_selected_files.txt"
        with open(selected_files_path, 'w') as f:
            for filename in filter_obj.selected_file_names:
                f.write(f"{filename}\n")
        logger.info(f"选中文件列表已保存: {selected_files_path}")
    
    return {
        'clustering_enabled': True,
        **clustering_results,
        'selected_files': filter_obj.selected_file_names
    }
