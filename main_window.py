# main_window.py
import sys
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QApplication
from PyQt5.QtCore import Qt

# 导入各个功能模块
from image_preprocessing import PreprocessingTab  # 预处理模块
from vegetation_index_tab import VegetationIndexTab
from texture_index_tab import TextureFeatureTab
from canopy_height_tab import CanopyHeightTab
from single_band_index_tab import SingleBandIndexTab
from custom_texture_tab import CustomTextureIndexTab
from custom_vegetation_index_tab import CustomVegetationIndexTab
from PyQt5.QtWidgets import QMainWindow
from custom_vegetation_index_tab import CustomVegetationIndexTab  # 确保导入正确
from Double_cropping_rice_PhenotypeIn_version_Module_tab import PhenotypeInversionTab  # 确保文件名和类名完全匹配

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("无人机田间表型高通量解析系统V1.0（UAV-FieldPhenoAnalyst V1.0）")
        self.resize(1200, 800)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint)

        # === 关键修复1：初始化状态栏 ===
        self.statusBar().showMessage("就绪", 3000)  # 必须调用！

        # === 关键修复2：按标准流程初始化 ===
        self._init_ui()          # 初始化主界面布局
        self._init_modules()     # 初始化所有功能模块
        self._setup_tabs()       # 添加所有选项卡

    def _init_ui(self):
        """初始化主窗口布局"""
        # 创建中央容器
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setMovable(False)
        self.setCentralWidget(self.tabs)

    def _init_modules(self):
        """初始化各功能模块实例（修复状态栏传递）"""
        # 植被相关模块
        self.single_band_tab = SingleBandIndexTab()
        self.prebuilt_veg_index_tab = VegetationIndexTab()
        self.custom_veg_index_tab = CustomVegetationIndexTab(main_window=self)  # 传递主窗口引用

        # 纹理相关模块
        self.texture_preprocessing_tab = PreprocessingTab()
        self.texture_feature_tab = TextureFeatureTab()
        self.custom_texture_tab = CustomTextureIndexTab()

        # 冠层高度提取模块
        self.canopy_height_tab = CanopyHeightTab()
        
        # 表型信息提取模块
        self.Double_cropping_rice_PhenotypeIn_version_tab = PhenotypeInversionTab()
        
    def _setup_tabs(self):
        """添加所有功能选项卡（按正确顺序）"""
        # 1. 植被指数模块
        self.tabs.addTab(self.single_band_tab, "单波段合成植被指数提取")
        self.tabs.addTab(self.prebuilt_veg_index_tab, "预合成植被指数提取")
        self.tabs.addTab(self.custom_veg_index_tab, "自定义合成植被指数提取")

        # 2. 纹理预处理模块
        self.tabs.addTab(self.texture_preprocessing_tab, "纹理特征提取影像预处理")

        # 3. 纹理特征模块
        self.tabs.addTab(self.texture_feature_tab, "纹理特征值提取")
        self.tabs.addTab(self.custom_texture_tab, "纹理指数提取")

        # 4. 冠层高度提取模块
        self.tabs.addTab(self.canopy_height_tab, "估算冠层高度提取")
        
        # 5. 冠层高度提取模块
        self.tabs.addTab(self.Double_cropping_rice_PhenotypeIn_version_tab, "华南双季稻表型参数获取")

        # 设置默认打开第一个选项卡
        self.tabs.setCurrentIndex(0)