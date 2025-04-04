import os
import pandas as pd
import joblib
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QFileDialog, QMessageBox, QProgressDialog,
                             QGroupBox, QComboBox, QHBoxLayout,QRadioButton)
from PyQt5.QtCore import Qt, pyqtSignal
import traceback
from PyQt5.QtWidgets import QCheckBox  # 添加到其他导入语句中

class PhenotypeInversionTab(QWidget):
    operation_completed = pyqtSignal(str)  # 操作完成信号

    def __init__(self):
        super().__init__()
        # 修改后的模型结构（关键修改1）
        self.models = {
            "早稻": {
                "冠层SPAD值（SPAD，幼穗分化期）": "幼穗分化期_早稻_SPAD_trained_model.pkl",
                "叶片氮积累量（LNA，幼穗分化期）": "幼穗分化期_早稻_LNA_trained_model.pkl",
                "植株氮积累量（PNA，幼穗分化期）": "幼穗分化期_早稻_PNA_trained_model.pkl",
                "地上部生物量（AGB，抽穗期）": "抽穗期_早稻_AGB_trained_model.pkl"
            },
            "晚稻": {
                "冠层SPAD值（SPAD，幼穗分化期）": "幼穗分化期_晚稻_SPAD_trained_model.pkl",
                "叶片氮积累量（LNA，幼穗分化期）": "幼穗分化期_晚稻_LNA_trained_model.pkl",
                "植株氮积累量（PNA，幼穗分化期）": "幼穗分化期_晚稻_PNA_trained_model.pkl",
                "地上部生物量（AGB，抽穗期）": "抽穗期_晚稻_AGB_trained_model.pkl"
            }
        }
        self.df = None
        self.init_ui()

    def init_ui(self):
        """初始化界面布局"""
        super().setStyleSheet("QGroupBox { font-size: 12px; }")
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # === 文件输入组 ===
        file_group = QGroupBox("特征文件输入")
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(8, 6, 8, 6)
        self.file_entry = QLineEdit()
        self.file_entry.setReadOnly(True)
        file_btn = QPushButton("浏览...")
        file_btn.setFixedWidth(75)
        file_btn.clicked.connect(self.load_csv)
        file_layout.addWidget(self.file_entry)
        file_layout.addWidget(file_btn)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # === 特征输入组 ===
        feature_group = QGroupBox("特征输入设置（分号分隔）")
        feature_grid = QGridLayout()
        feature_grid.setVerticalSpacing(4)
        feature_grid.setContentsMargins(10, 10, 10, 10)
        feature_grid.setColumnStretch(1, 2)

        # 初始化输入框和标签
        self.spec_entry = QLineEdit()
        self.texture_entry = QLineEdit()
        self.struct_entry = QLineEdit()
        self.cultivar_entry = QLineEdit()

        # 设置输入框样式
        entry_style = "QLineEdit { padding: 5px; font-size: 12px; }"
        for entry in [self.spec_entry, self.texture_entry, self.struct_entry, self.cultivar_entry]:
            entry.setStyleSheet(entry_style)

        # 添加标签和输入框
        feature_grid.addWidget(QLabel("光谱特征:"), 0, 0)
        feature_grid.addWidget(self.spec_entry, 0, 1)
        feature_grid.addWidget(QLabel("纹理特征:"), 2, 0)
        feature_grid.addWidget(self.texture_entry, 2, 1)
        feature_grid.addWidget(QLabel("结构特征:"), 4, 0)
        feature_grid.addWidget(self.struct_entry, 4, 1)
        feature_grid.addWidget(QLabel("栽培因子:"), 6, 0)
        feature_grid.addWidget(self.cultivar_entry, 6, 1)

        # 添加提示标签
        tip_style = "color: #666; font-size: 11px;"
        feature_grid.addWidget(QLabel("提示：单波段反射率，植被指数等", styleSheet=tip_style), 1, 1)
        feature_grid.addWidget(QLabel("提示：纹理特征值，纹理指数等", styleSheet=tip_style), 3, 1)
        feature_grid.addWidget(QLabel("提示：冠层高度，冠层体积等", styleSheet=tip_style), 5, 1)
        feature_grid.addWidget(QLabel("提示：氮肥施用量，种植密度等", styleSheet=tip_style), 7, 1)
        
        feature_group.setLayout(feature_grid)
        main_layout.addWidget(feature_group)

        # === 模型选择组 ===
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout()
        model_layout.setContentsMargins(10, 15, 10, 15)
        model_layout.setSpacing(15)

        # 稻作类型选择（横向单选框）
        crop_group = QGroupBox("稻作类型")
        crop_layout = QHBoxLayout()
        self.early_rb = QRadioButton("早稻")
        self.late_rb = QRadioButton("晚稻")
        self.early_rb.setChecked(True)
        crop_layout.addWidget(self.early_rb)
        crop_layout.addWidget(self.late_rb)
        crop_group.setLayout(crop_layout)
        model_layout.addWidget(crop_group)

        # 目标参数选择（动态横向单选框）
        self.param_group = QGroupBox("目标参数")
        self.param_layout = QHBoxLayout()
        self.param_buttons = []
        self.update_params()  # 初始化参数选项
        self.param_group.setLayout(self.param_layout)
        model_layout.addWidget(self.param_group)

        model_group.setLayout(model_layout)
        main_layout.addWidget(model_group)

        # === 输出路径组 ===
        output_group = QGroupBox("输出设置")
        output_layout = QHBoxLayout()
        self.output_entry = QLineEdit()
        self.output_entry.setPlaceholderText("请选择输出文件夹")
        self.output_entry.setReadOnly(True)
        output_btn = QPushButton("浏览...")
        output_btn.setFixedWidth(75)
        output_btn.clicked.connect(self.select_output_path)
        output_layout.addWidget(self.output_entry)
        output_layout.addWidget(output_btn)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        # === 运行按钮 ===
        self.run_btn = QPushButton("▶ 开始预测")
        self.run_btn.setStyleSheet(
            "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
            "QPushButton:hover{background:#45a049;}"
        )
        self.run_btn.clicked.connect(self.run_prediction)
        main_layout.addWidget(self.run_btn, alignment=Qt.AlignCenter)

        # 连接信号
        self.early_rb.toggled.connect(self.update_params)
        self.late_rb.toggled.connect(self.update_params)

        self.setLayout(main_layout)
        
    def update_models(self):
        """更新目标参数勾选框"""
        # 清空现有复选框
        while self.param_checkbox_layout.count():
            item = self.param_checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取当前稻作类型
        crop_type = self.crop_type_combo.currentText()
        
        # 添加新的复选框
        for param in self.models[crop_type].keys():
            checkbox = QCheckBox(param)
            self.param_checkbox_layout.addWidget(checkbox)

    def load_csv(self):
        """加载CSV文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv)")
        if path:
            try:
                self.df = pd.read_csv(path)
                self.file_entry.setText(path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"文件读取失败:\n{str(e)}")

    def select_output_path(self):
        """选择输出路径"""
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if path:
            self.output_entry.setText(path)

    def validate_inputs(self):
        """输入验证"""
        errors = []
        
        # 稻作类型检查
        if not self.early_rb.isChecked() and not self.late_rb.isChecked():
            errors.append("必须选择一个稻作类型")
        elif self.early_rb.isChecked() and self.late_rb.isChecked():
            errors.append("不能同时选择早稻和晚稻")

        # 目标参数检查
        if not self.get_selected_param():
            errors.append("必须选择一个目标参数")

        # 文件检查
        if not self.file_entry.text():
            errors.append("请先选择特征文件")
        elif self.df is None:
            errors.append("文件加载失败，请重新选择文件")
        else:
            # 特征列存在性检查（新增关键检查）
            required_features = {
                "SPAD": ['RVI', 'NDVI', 'DCNI', 'SA'],
                "LNA": ['OSAVI', 'MSAVI', 'NDVI', '种植密度'],
                "PNA": ['MSAVI', 'RDVI', '种植密度', '施氮量'],
                "AGB": ['株高', '茎粗', 'LAI', 'NDVI']
            }
            selected_key = self.get_selected_param().split('（')[1].split('，')[0]
            features = required_features.get(selected_key, [])
            missing = [f for f in features if f not in self.df.columns]
            if missing:
                errors.append(f"缺失{selected_key}模型必需特征：{', '.join(missing)}")
        
        # 输出路径检查
        if not self.output_entry.text():
            errors.append("请选择输出路径")
        elif not os.path.exists(self.output_entry.text()):
            errors.append("输出路径不存在，请重新选择")

        if errors:
            QMessageBox.critical(self, "输入错误", "发现以下问题：\n\n• " + "\n• ".join(errors))
            return False
        return True
    
    def run_prediction(self):
            """执行预测流程"""
            if not self.validate_inputs():
                return

            progress = QProgressDialog("正在执行预测...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            
            try:
                # 获取选中参数（关键修改2）
                crop_type = "早稻" if self.early_rb.isChecked() else "晚稻"
                selected_param = self.get_selected_param()
                model_path = self.models[crop_type][selected_param]

                # 加载模型（关键修改3）
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"模型文件未找到：{model_path}")
                    
                model = joblib.load(model_path)
                progress.setValue(30)
                
                # 准备数据
                X = self.df[self.get_features()]
                progress.setValue(50)
                
                # 预测
                predictions = model.predict(X)
                output_df = self.df.copy()
                output_df[f"预测_{selected_param.split('（')[0]}"] = predictions
                progress.setValue(80)
                
                # 保存结果
                output_dir = self.output_entry.text()
                filename = f"{crop_type}_{selected_param.split('（')[1].split('，')[0]}_预测结果.csv"
                output_path = os.path.join(output_dir, filename)
                output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                progress.setValue(100)

                self.operation_completed.emit(output_dir)
                QMessageBox.information(self, "完成", f"预测结果已保存至：\n{output_path}")

            except Exception as e:
                QMessageBox.critical(
                    self, "错误", 
                    f"预测失败: {str(e)}\n\n{traceback.format_exc()}"
                )
            finally:
                progress.close()

            
    def get_selected_param(self):
        """获取选中的目标参数"""
        for rb in self.param_buttons:
            if rb.isChecked():
                return rb.text()
        return None

    
    
    def update_params(self):
        """更新目标参数单选框"""
        # 清空现有单选框
        for btn in self.param_buttons:
            btn.deleteLater()
        self.param_buttons.clear()

        # 获取当前稻作类型
        crop_type = "早稻" if self.early_rb.isChecked() else "晚稻"
        
        # 创建新的单选框
        for param in self.models[crop_type].keys():
            rb = QRadioButton(param)
            self.param_layout.addWidget(rb)
            self.param_buttons.append(rb)
        
        # 默认选中第一个参数
        if self.param_buttons:
            self.param_buttons[0].setChecked(True)