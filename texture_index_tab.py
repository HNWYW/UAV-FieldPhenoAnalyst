# texture_index_tab.py
import os
import numpy as np
import skimage.io
import cv2
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QScrollArea, QMessageBox, QFileDialog,
    QGroupBox, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from get_glcm import (
    calcu_glcm, calcu_glcm_mean, calcu_glcm_variance,
    calcu_glcm_homogeneity, calcu_glcm_contrast,
    calcu_glcm_dissimilarity, calcu_glcm_entropy,
    calcu_glcm_correlation, calcu_glcm_Second_Moment,
    Edge_Remove, calcu_txt_mean
)

class CalculationThread(QThread):
    progress_updated = pyqtSignal(int, int, str)
    calculation_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, root_path, window_sizes, features, output_path, parent=None):
            super().__init__(parent)
            self.root_path = root_path
            self.window_sizes = [ws for ws in window_sizes if ws % 2 == 1]
            self.features = features
            self.output_path = output_path  # 新增输出路径
            self._is_running = True

    def run(self):
        try:
            all_files = []
            valid_extensions = ('.tif', '.tiff', '.png', '.jpg', '.jpeg')
            for root, _, files in os.walk(self.root_path):
                for file in files:
                    if file.lower().endswith(valid_extensions):
                        full_path = os.path.join(root, file)
                        if os.path.getsize(full_path) > 0:
                            all_files.append(full_path)
                        else:
                            self.error_occurred.emit(f"空文件: {file}")

            total = len(all_files) * len(self.window_sizes)
            processed = 0

            for img_path in all_files:
                if not self._is_running:
                    break

                for window_size in self.window_sizes:
                    try:
                        results = self.process_image(img_path, window_size)
                        self.save_results(img_path, window_size, results)
                        processed += 1
                        self.progress_updated.emit(
                            processed, total, 
                            f"{os.path.basename(img_path)} ({window_size}x{window_size})"
                        )
                    except Exception as e:
                        self.error_occurred.emit(
                            f"处理失败: {os.path.basename(img_path)}\n"
                            f"窗口大小: {window_size}x{window_size}\n"
                            f"错误详情: {str(e)}"
                        )
                        continue

            self.calculation_finished.emit()

        except Exception as e:
            self.error_occurred.emit(f"运行时错误: {str(e)}")
        finally:
            self._cleanup()

    def _cleanup(self):
        if hasattr(self, 'temp_files'):
            for f in self.temp_files:
                try: os.remove(f)
                except: pass

    def stop(self):
        self._is_running = False
        self.wait(5000)

    def process_image(self, img_path, window_size):
        # 增强图像读取
        try:
            img = skimage.io.imread(img_path, as_gray=True)
            if img is None or img.size == 0:
                raise ValueError("无效的图像数据")
        except Exception as e:
            raise ValueError(f"图像读取失败: {str(e)}")

        # 改进的归一化处理
        img_min = np.min(img)
        img_max = np.max(img)
        if img_max - img_min < 1e-8:
            raise ValueError("图像灰度范围不足")

        img_norm = np.uint8(255.0 * (img - img_min) / (img_max - img_min + 1e-8))

        # GLCM参数设置（与原始代码严格一致）
        glcm_params = {
            'mi': 0,
            'ma': 255,
            'nbit': 64,
            'slide_window': window_size,
            'step': [1],         # 原始代码固定参数
            'angle': [0, np.pi/4, np.pi/2, 3*np.pi/4]  # 四个方向
        }

        try:
            glcm = calcu_glcm(img_norm, **glcm_params)
        except Exception as e:
            raise ValueError(f"GLCM计算失败: {str(e)}")

        # 特征计算（修复维度问题）
        feature_processors = {
            "MEA": (calcu_glcm_mean, 0, 0),
            "VAR": (calcu_glcm_variance, 0, 0),
            "HOM": (calcu_glcm_homogeneity, 1, 1),
            "CON": (calcu_glcm_contrast, 0, 0),
            "DIS": (calcu_glcm_dissimilarity, 0, 0),
            "ENT": (calcu_glcm_entropy, 0, 0),
            "COR": (calcu_glcm_correlation, 0, 0),
            "SEM": (calcu_glcm_Second_Moment, 1, 1)
        }

        results = {}
        for feature in self.features:
            if feature not in feature_processors:
                continue

            func, edge_val, mean_val = feature_processors[feature]
            try:
                # 关键修复：处理多方向数据
                feature_data = []
                for i in range(glcm.shape[2]):  # step维度
                    for j in range(glcm.shape[3]):  # angle维度
                        glcm_slice = glcm[:, :, i, j, :, :]
                        data = func(glcm_slice, 64)
                        feature_data.append(data)
                
                # 平均所有方向和步长（与原始代码逻辑一致）
                avg_feature = np.mean(feature_data, axis=0)
                cleaned_data = Edge_Remove(avg_feature, edge_val)
                final_value = calcu_txt_mean(cleaned_data, mean_val)
                results[feature] = final_value
            except Exception as e:
                raise ValueError(f"特征[{feature}]计算失败: {str(e)}")

        return results



    def save_results(self, img_path, window_size, results):
        try:
            output_dir = self.output_path  # 使用传递的输出路径
            if not output_dir:
                raise ValueError("请选择输出文件夹路径")

            # 获取图像的波段信息（文件名如 Red, Green, Blue）
            band_name = 'Unknown'
            if 'Red' in img_path:
                band_name = 'R'
            elif 'Green' in img_path:
                band_name = 'G'
            elif 'Blue' in img_path:
                band_name = 'B'
            elif 'RedEdge' in img_path:
                band_name = 'RE'
            elif 'NIR' in img_path:
                band_name = 'NIR'

            # 生成波段文件夹路径
            band_dir = os.path.join(output_dir, band_name)
            os.makedirs(band_dir, exist_ok=True)

            # 生成以窗口尺寸为基础的子文件夹
            window_dir = os.path.join(band_dir, f"{window_size}x{window_size}")
            os.makedirs(window_dir, exist_ok=True)

            # 生成特征名称列，如 B_VAR, R_VAR 等
            feature_columns = {f"{band_name}_{feature}": value for feature, value in results.items()}

            # 将文件名和计算的特征保存为数据
            record = {
                "FileName": os.path.basename(img_path),
                "WindowSize": window_size,
                **feature_columns
            }

            # 生成CSV文件路径
            output_file = os.path.join(window_dir, "texture_features.csv")

            df = pd.DataFrame([record])

            write_header = not os.path.exists(output_file)
            df.to_csv(output_file, mode='a', header=write_header, index=False)
        except Exception as e:
            raise IOError(f"结果保存失败: {str(e)}")

    



class TextureFeatureTab(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.thread = None
        self.setWindowTitle("纹理特征计算 v2.1")
        # self.setMinimumSize(1200, 900)


    def initUI(self):
        main_layout = QVBoxLayout()
        
        # === 参数设置组 ===
        param_group = QGroupBox("计算参数设置")
        param_grid = QGridLayout()

        # === 修改点1：添加路径提示 ===
        # 目录选择
        self.dir_label = QLabel("输入文件夹路径:")
        self.dir_edit = QLineEdit()
        self.dir_btn = QPushButton("浏览")
        self.dir_btn.clicked.connect(self.browse_directory)
        
        # 新增提示标签
        self.dir_hint = QLabel("<font color='gray'>提示：请确保子文件夹按波段命名（Red/Green/Blue/RedEdge/NIR）</font>")
        self.dir_hint.setAlignment(Qt.AlignLeft)

        param_grid.addWidget(self.dir_label, 0, 0)
        param_grid.addWidget(self.dir_edit, 0, 1)
        param_grid.addWidget(self.dir_btn, 0, 2)
        param_grid.addWidget(self.dir_hint, 1, 0, 1, 3)  # 占据新行

        # === 修改点2：调整布局行号 ===
        # 窗口尺寸选择
        self.window_group = QGroupBox("窗口尺寸选择")
        window_layout = QHBoxLayout()
        self.window_checks = {
            3: QCheckBox("3x3"), 5: QCheckBox("5x5"),
            7: QCheckBox("7x7"), 9: QCheckBox("9x9"),
            11: QCheckBox("11x11"), 13: QCheckBox("13x13"),
            15: QCheckBox("15x15"), 17: QCheckBox("17x17")
        }
        for cb in self.window_checks.values():
            window_layout.addWidget(cb)
        self.window_group.setLayout(window_layout)
        param_grid.addWidget(self.window_group, 2, 0, 1, 3)  # 原1→2

        # === 修改点3：特征选择布局 ===
        self.feature_group = QGroupBox("纹理特征选择")
        feature_scroll = QScrollArea()
        feature_scroll.setWidgetResizable(True)
        feature_widget = QWidget()
        
        # 新布局设置
        feature_layout = QGridLayout()
        feature_layout.setHorizontalSpacing(2)  # 列间距
        feature_layout.setVerticalSpacing(2)     # 行间距
        feature_layout.setContentsMargins(2, 2, 2, 2)

        self.feature_checks = {
            "MEA": QCheckBox("均值 (MEA)"),
            "VAR": QCheckBox("方差 (VAR)"),
            "HOM": QCheckBox("同质性 (HOM)"),
            "CON": QCheckBox("对比度 (CON)"),
            "DIS": QCheckBox("相异性 (DIS)"),
            "ENT": QCheckBox("熵 (ENT)"),
            "COR": QCheckBox("相关性 (COR)"),
            "SEM": QCheckBox("二阶矩 (SEM)")
        }

        # 每行4列的布局
        row = col = 0
        for idx, cb in enumerate(self.feature_checks.values()):
            feature_layout.addWidget(cb, row, col)
            col += 1
            if col >= 4:  # 每行4个
                col = 0
                row += 1

        feature_widget.setLayout(feature_layout)
        feature_scroll.setWidget(feature_widget)
        self.feature_group.setLayout(QVBoxLayout())
        self.feature_group.layout().addWidget(feature_scroll)
        param_grid.addWidget(self.feature_group, 3, 0, 1, 3)  # 原2→3

        # 输出路径（行号调整）
        self.output_label = QLabel("输出文件夹路径:")
        self.output_edit = QLineEdit()
        self.output_btn = QPushButton("浏览")
        self.output_btn.clicked.connect(self.browse_output_directory)
        param_grid.addWidget(self.output_label, 4, 0)  # 原3→4
        param_grid.addWidget(self.output_edit, 4, 1)
        param_grid.addWidget(self.output_btn, 4, 2)

        param_group.setLayout(param_grid)
        main_layout.addWidget(param_group)

        # === 进度控制组 ===
        control_group = QGroupBox("计算控制")
        control_layout = QVBoxLayout()
        
        self.progress_info = QLabel("准备就绪")
        self.progress_count = QLabel("0 / 0")
        self.progress_info.setAlignment(Qt.AlignCenter)
        self.progress_count.setAlignment(Qt.AlignCenter)
        
        self.start_btn = QPushButton("开始计算")
        self.stop_btn = QPushButton("停止计算")
        # 设置样式
        self.start_btn.setStyleSheet(
            "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
            "QPushButton:hover{background:#45a049;}"
        )

        self.stop_btn.setStyleSheet(
            "QPushButton{font-size:12pt; padding:8px; background:#f44336; color:white;}"
            "QPushButton:hover{background:#e53935;}"
)
        self.start_btn.clicked.connect(self.start_calculation)
        self.stop_btn.clicked.connect(self.stop_calculation)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        
        control_layout.addWidget(self.progress_info)
        control_layout.addWidget(self.progress_count)
        control_layout.addLayout(btn_layout)
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        self.setLayout(main_layout)

    def browse_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择数据目录")
        if path:
            self.dir_edit.setText(path)
            self.progress_info.setText(f"已选择目录: {os.path.basename(path)}")


    def browse_output_directory(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if path:
            self.output_edit.setText(path)
            self.progress_info.setText(f"已选择输出目录: {os.path.basename(path)}")



    def start_calculation(self):
        root_path = self.dir_edit.text()
        output_path = self.output_edit.text()  # 获取输出路径
        if not os.path.isdir(root_path):
            QMessageBox.warning(self, "错误", "请选择有效的数据目录")
            return

        if not output_path:
            QMessageBox.warning(self, "错误", "请选择有效的输出文件夹路径")
            return

        selected_windows = [s for s, cb in self.window_checks.items() if cb.isChecked()]
        if not selected_windows:
            QMessageBox.warning(self, "错误", "请至少选择一个窗口尺寸")
            return

        selected_features = [f for f, cb in self.feature_checks.items() if cb.isChecked()]
        if not selected_features:
            QMessageBox.warning(self, "错误", "请至少选择一个纹理特征")
            return

        # 启动线程并传递输出路径
        self.thread = CalculationThread(
            root_path=root_path,
            window_sizes=selected_windows,
            features=selected_features,
            output_path=output_path  # 传递输出路径
        )

        self.thread.progress_updated.connect(self.update_progress)
        self.thread.calculation_finished.connect(self.calculation_complete)
        self.thread.error_occurred.connect(self.show_error)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_info.setText("计算进行中...")
        self.thread.start()


    def stop_calculation(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_info.setText("计算已中止")

    def update_progress(self, current, total, filename):
        self.progress_count.setText(f"{current}/{total}")
        self.progress_info.setText(f"正在处理: {filename}")

    def calculation_complete(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_info.setText("计算完成")
        QMessageBox.information(self, "完成", "所有特征计算已完成！")

    def show_error(self, message):
        QMessageBox.critical(self, "错误", message)
        self.stop_calculation()

    def closeEvent(self, event):
        self.stop_calculation()
        event.accept()
