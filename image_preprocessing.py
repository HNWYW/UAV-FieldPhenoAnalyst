# image_preprocessing.py
import os
import sys  # 新增sys导入
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import pyproj
from shapely.geometry import mapping
from shapely.ops import transform as shapely_transform
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QMessageBox, QFileDialog, QGroupBox,
    QApplication  # 确保包含QApplication
)

class PreprocessingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setWindowTitle("纹理图像预处理工具")
        self.setMinimumSize(800, 600)

    def initUI(self):
        main_layout = QVBoxLayout()
        
        # === 预处理参数组 ===
        preprocess_group = QGroupBox("预处理设置")
        pre_grid = QGridLayout()

        # 矢量文件
        self.shp_label = QLabel("矢量文件 (shp):")
        self.shp_edit = QLineEdit()
        self.shp_btn = QPushButton("浏览")
        self.shp_btn.clicked.connect(self.browse_shp)
        pre_grid.addWidget(self.shp_label, 0, 0)
        pre_grid.addWidget(self.shp_edit, 0, 1)
        pre_grid.addWidget(self.shp_btn, 0, 2)

        # 单影像输入
        self.single_tif_label = QLabel("单影像处理 (tif):")
        self.single_tif_edit = QLineEdit()
        self.single_tif_btn = QPushButton("浏览")
        self.single_tif_btn.clicked.connect(lambda: self.browse_tif(single=True))
        pre_grid.addWidget(self.single_tif_label, 1, 0)
        pre_grid.addWidget(self.single_tif_edit, 1, 1)
        pre_grid.addWidget(self.single_tif_btn, 1, 2)

        # 多影像输入
        self.multi_tif_label = QLabel("多影像批处理 (tif):")
        self.multi_tif_edit = QTextEdit()
        self.multi_tif_edit.setPlaceholderText("支持拖放或分号分隔多个路径")
        self.multi_tif_btn = QPushButton("浏览")
        self.multi_tif_btn.clicked.connect(self.browse_multiple_tif)
        pre_grid.addWidget(self.multi_tif_label, 2, 0)
        pre_grid.addWidget(self.multi_tif_edit, 2, 1, 2, 1)
        pre_grid.addWidget(self.multi_tif_btn, 2, 2)

        # 输出目录
        self.output_label = QLabel("预处理输出目录:")
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("浏览")
        self.output_btn.clicked.connect(self.browse_output)
        pre_grid.addWidget(self.output_label, 4, 0)
        pre_grid.addWidget(self.output_edit, 4, 1)
        pre_grid.addWidget(self.output_btn, 4, 2)

        # 预处理按钮
        self.preprocess_btn = QPushButton("▶ 执行预处理")
        self.preprocess_btn.setStyleSheet(
        "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
        "QPushButton:hover{background:#45a049;}"
        )
        self.preprocess_btn.clicked.connect(self.run_preprocessing)
        pre_grid.addWidget(self.preprocess_btn, 5, 1)

        preprocess_group.setLayout(pre_grid)
        main_layout.addWidget(preprocess_group)
        self.setLayout(main_layout)

    # region 文件操作
    def browse_shp(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择矢量文件", "", "Shapefile (*.shp)")
        if path:
            self.shp_edit.setText(path)

    def browse_tif(self, single=True):
        if single:
            path, _ = QFileDialog.getOpenFileName(self, "选择单影像文件", "", "TIFF文件 (*.tif *.tiff)")
            if path:
                self.single_tif_edit.setText(path)

    def browse_multiple_tif(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多个影像文件", "", "TIFF文件 (*.tif *.tiff);;所有文件 (*)")
        if files:
            existing = self.parse_multi_tif_paths()
            new_files = "\n".join([f for f in files if f not in existing])
            self.multi_tif_edit.append(new_files)

    def parse_multi_tif_paths(self):
        return [p.strip() for p in self.multi_tif_edit.toPlainText().replace(';','\n').splitlines() if p.strip()]

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_edit.setText(path)
    # endregion

    # region 预处理逻辑
    def run_preprocessing(self):
        errors = []
        shp_path = self.shp_edit.text()
        output_root = self.output_edit.text()
        single_tif = self.single_tif_edit.text()
        multi_tifs = self.parse_multi_tif_paths()

        if not shp_path: errors.append("必须选择矢量文件")
        if not output_root: errors.append("必须指定输出目录")
        if not single_tif and not multi_tifs: errors.append("至少需要选择一个影像文件")
        
        if errors:
            QMessageBox.warning(self, "输入错误", "\n".join(errors))
            return

        try:
            gdf = gpd.read_file(shp_path)
            tif_files = [single_tif] if single_tif else []
            tif_files.extend(multi_tifs)

            total = len(tif_files)
            processed = 0
            self.preprocess_btn.setEnabled(False)

            for tif_path in tif_files:
                if not os.path.exists(tif_path):
                    raise FileNotFoundError(f"文件不存在: {tif_path}")

                with rasterio.open(tif_path) as src:
                    transformer = None
                    if str(gdf.crs) != str(src.crs):
                        transformer = pyproj.Transformer.from_crs(
                            pyproj.CRS(str(gdf.crs)),
                            pyproj.CRS(str(src.crs)),
                            always_xy=True
                        )

                    tif_name = os.path.splitext(os.path.basename(tif_path))[0]
                    output_dir = os.path.join(output_root, tif_name)
                    os.makedirs(output_dir, exist_ok=True)

                    for name_value, group in gdf.groupby("name"):
                        try:
                            geometries = []
                            for geom in group.geometry:
                                try:
                                    if transformer:
                                        transformed = shapely_transform(transformer.transform, geom)
                                        geometries.append(mapping(transformed))
                                    else:
                                        geometries.append(mapping(geom))
                                except Exception as ge:
                                    print(f"几何转换错误: {str(ge)}")
                                    continue

                            try:
                                out_image, out_transform = mask(src, geometries, crop=True)
                            except ValueError as ve:
                                print(f"跳过无交集区域: {name_value} - {str(ve)}")
                                continue

                            meta = src.meta.copy()
                            meta.update({
                                "driver": "GTiff",
                                "height": out_image.shape[1],
                                "width": out_image.shape[2],
                                "transform": out_transform,
                                "nodata": 0
                            })

                            out_image = np.where(out_image == src.nodata, 0, out_image)
                            output_path = os.path.join(output_dir, f"{name_value}.tif")
                            with rasterio.open(output_path, "w", **meta) as dest:
                                dest.write(out_image)

                        except Exception as e:
                            print(f"处理 {name_value} 时出错: {str(e)}")
                            continue

                processed += 1
                self.preprocess_btn.setText(f"预处理进度 ({processed}/{total})")
                QApplication.processEvents()  # 现在QApplication已正确初始化

            QMessageBox.information(self, "完成", f"成功处理{processed}个影像！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"预处理失败: {str(e)}")
        finally:
            self.preprocess_btn.setEnabled(True)
            self.preprocess_btn.setText("执行预处理")
    # endregion