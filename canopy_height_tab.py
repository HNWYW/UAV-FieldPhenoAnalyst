# 导入GUI相关库
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                            QLineEdit, QPushButton, QFileDialog, QMessageBox)
# 导入数据处理相关库
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import pandas as pd
from shapely.geometry import mapping  # 几何对象序列化

class CanopyHeightTab(QWidget):
    """冠层高度计算主界面"""
    def __init__(self):
        super().__init__()
        self.initUI()  # 初始化界面

    def initUI(self):
        """界面布局初始化"""
        # 主布局使用垂直排列
        main_layout = QVBoxLayout()
        
        # === 输入参数部分 ===
        # 使用网格布局排列输入组件
        grid = QGridLayout()

        # 矢量文件输入
        self.shp_label = QLabel("矢量文件 (shp):")
        self.shp_edit = QLineEdit()
        self.shp_browse_btn = QPushButton("浏览")
        self.shp_browse_btn.clicked.connect(lambda: self.browse_file(self.shp_edit, "选择矢量文件", "Shapefile (*.shp)"))
        grid.addWidget(self.shp_label, 0, 0)
        grid.addWidget(self.shp_edit, 0, 1)
        grid.addWidget(self.shp_browse_btn, 0, 2)

        # 冠层DSM文件输入
        self.canopy_label = QLabel("冠层数字表面模型文件（DSM）:")
        self.canopy_edit = QLineEdit()
        self.canopy_browse_btn = QPushButton("浏览")
        self.canopy_browse_btn.clicked.connect(lambda: self.browse_file(self.canopy_edit, "选择冠层DSM文件", "TIFF files (*.tif *.tiff)"))
        grid.addWidget(self.canopy_label, 1, 0)
        grid.addWidget(self.canopy_edit, 1, 1)
        grid.addWidget(self.canopy_browse_btn, 1, 2)

        # 裸地DSM文件输入
        self.bare_label = QLabel("裸地数字表面模型文件（DSM）:")
        self.bare_edit = QLineEdit()
        self.bare_browse_btn = QPushButton("浏览")
        self.bare_browse_btn.clicked.connect(lambda: self.browse_file(self.bare_edit, "选择裸地DSM文件", "TIFF files (*.tif *.tiff)"))
        grid.addWidget(self.bare_label, 2, 0)
        grid.addWidget(self.bare_edit, 2, 1)
        grid.addWidget(self.bare_browse_btn, 2, 2)

        # 百分位数输入
        self.canopy_percent_label = QLabel("冠层DSM百分位数（%）:")
        self.canopy_percent_edit = QLineEdit("99")
        self.canopy_percent_edit.setFixedWidth(50)
        grid.addWidget(self.canopy_percent_label, 3, 0)
        grid.addWidget(self.canopy_percent_edit, 3, 1)

        self.bare_percent_label = QLabel("裸地DSM百分位数（%）:")
        self.bare_percent_edit = QLineEdit("1")
        self.bare_percent_edit.setFixedWidth(50)
        grid.addWidget(self.bare_percent_label, 4, 0)
        grid.addWidget(self.bare_percent_edit, 4, 1)

        main_layout.addLayout(grid)

        # === 运行按钮 ===
        self.run_btn = QPushButton("计算估测冠层高度")
        self.run_btn.setStyleSheet(
        "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
        "QPushButton:hover{background:#45a049;}"
        )
        self.run_btn.clicked.connect(self.run_calculation)
        main_layout.addWidget(self.run_btn)

        self.setLayout(main_layout)

    def browse_file(self, edit_widget, title, file_filter):
        """通用文件浏览方法"""
        filename, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if filename:
            edit_widget.setText(filename)

    def validate_inputs(self):
        """输入参数验证"""
        # 检查文件路径是否有效
        required_files = [
            (self.shp_edit.text(), "矢量文件"),
            (self.canopy_edit.text(), "冠层DSM文件"),
            (self.bare_edit.text(), "裸地DSM文件")
        ]
        
        for path, name in required_files:
            if not path:
                QMessageBox.critical(self, "错误", f"请选择{name}！")
                return False
            if not path.lower().endswith(('.shp', '.tif', '.tiff')):
                QMessageBox.critical(self, "错误", f"{name}格式不正确！")
                return False

        # 检查百分位数数值有效性
        try:
            canopy_percent = float(self.canopy_percent_edit.text())
            bare_percent = float(self.bare_percent_edit.text())
            if not (0 <= canopy_percent <= 100) or not (0 <= bare_percent <= 100):
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "错误", "百分位数必须是0-100之间的数字！")
            return False

        return True

    def run_calculation(self):
        """执行计算主函数"""
        if not self.validate_inputs():
            return

        try:
            # 收集输入参数
            params = {
                "shp_path": self.shp_edit.text(),
                "canopy_dsm": self.canopy_edit.text(),
                "bare_dsm": self.bare_edit.text(),
                "canopy_percent": float(self.canopy_percent_edit.text()),
                "bare_percent": float(self.bare_percent_edit.text())
            }

            # 执行计算
            results = self.calculate_canopy_height(params)

            # 保存结果
            save_path, _ = QFileDialog.getSaveFileName(self, "保存结果", "", "CSV文件 (*.csv)")
            if save_path:
                results.to_csv(save_path, index=False)
                QMessageBox.information(self, "完成", f"结果已保存至：{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算过程中发生错误：\n{str(e)}")

    def calculate_canopy_height(self, params):
        """核心计算逻辑"""
        # 读取矢量数据
        gdf = gpd.read_file(params["shp_path"])
        
        # 坐标系检查与重投影
        with rasterio.open(params["canopy_dsm"]) as src:
            raster_crs = src.crs

        if gdf.crs != raster_crs:
            gdf = gdf.to_crs(raster_crs)

        results = []

        # 同时打开两个DSM文件
        with rasterio.open(params["bare_dsm"]) as bare_src, \
             rasterio.open(params["canopy_dsm"]) as canopy_src:

            # 获取nodata值
            bare_nodata = bare_src.nodata
            canopy_nodata = canopy_src.nodata

            # 遍历每个多边形
            for idx, row in gdf.iterrows():
                geom = row['geometry']
                geom_json = [mapping(geom)]  # 转换为GeoJSON格式

                # 处理裸地DSM
                try:
                    bare_data, _ = mask(bare_src, geom_json, crop=True)
                    bare_array = bare_data[0]
                    if bare_nodata is not None:
                        valid_bare = bare_array[bare_array != bare_nodata]
                    else:
                        valid_bare = bare_array[~np.isnan(bare_array)]
                    bare_value = np.percentile(valid_bare, params["bare_percent"]) if valid_bare.size > 0 else np.nan
                except Exception as e:
                    bare_value = np.nan

                # 处理冠层DSM
                try:
                    canopy_data, _ = mask(canopy_src, geom_json, crop=True)
                    canopy_array = canopy_data[0]
                    if canopy_nodata is not None:
                        valid_canopy = canopy_array[canopy_array != canopy_nodata]
                    else:
                        valid_canopy = canopy_array[~np.isnan(canopy_array)]
                    canopy_value = np.percentile(valid_canopy, params["canopy_percent"]) if valid_canopy.size > 0 else np.nan
                except Exception as e:
                    canopy_value = np.nan

                # 计算冠层高度
                height = canopy_value - bare_value if not np.isnan(canopy_value) and not np.isnan(bare_value) else np.nan

                results.append({
                    "区域ID": row.get('Id', idx),
                    "裸地高程": bare_value,
                    "冠层高程": canopy_value,
                    "冠层高度": height
                })

        return pd.DataFrame(results)