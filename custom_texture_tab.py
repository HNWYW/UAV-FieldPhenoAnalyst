import os
import json
import numpy as np
import pandas as pd
from itertools import product
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QScrollArea, QMessageBox, QFileDialog, 
    QListWidget, QAbstractItemView, QGroupBox,  # 添加QGroupBox
    QApplication)  # 添加QApplication
from PyQt5.QtCore import Qt

class CustomTextureIndexTab(QWidget):
    def __init__(self):
        super().__init__()
        self.customIndicesFile = "custom_texture_indices.json"
        self.textureOptions = {}
        self.csv_path = ""
        self.all_features = []  # 存储所有特征列
        
        layout = QVBoxLayout()
        
        # CSV文件选择部分
        csvLayout = QVBoxLayout()
        row1 = QHBoxLayout()
        self.csvLabel = QLabel("输入CSV文件:")
        self.csvLineEdit = QLineEdit()
        self.csvBrowseButton = QPushButton("浏览")
        self.csvBrowseButton.clicked.connect(self.browseCsv)
        
        row1.addWidget(self.csvLabel)
        row1.addWidget(self.csvLineEdit)
        row1.addWidget(self.csvBrowseButton)
        
        self.csvHint = QLabel("<font color='gray'>提示：CSV应包含ID列和波段纹理特征值（列名格式：波段_特征，如B_VAR）</font>")
        csvLayout.addLayout(row1)
        csvLayout.addWidget(self.csvHint)
        layout.addLayout(csvLayout)

        # 特征选择模式
        self.modeGroup = QGroupBox("计算模式")
        mode_layout = QHBoxLayout()
        self.singleMode = QCheckBox("单特征模式")
        self.multiMode = QCheckBox("多特征组合模式")
        self.fullMode = QCheckBox("全特征组合模式")
        self.singleMode.setChecked(True)
        
        mode_layout.addWidget(self.singleMode)
        mode_layout.addWidget(self.multiMode)
        mode_layout.addWidget(self.fullMode)
        self.modeGroup.setLayout(mode_layout)
        layout.addWidget(self.modeGroup)

        # 单特征模式输入
        self.singleParamGroup = QGroupBox("单特征参数")
        paramLayout = QGridLayout()
        self.t1Label = QLabel("T1特征:")
        self.t1Input = QLineEdit()
        self.t2Label = QLabel("T2特征:")
        self.t2Input = QLineEdit()
        
        paramLayout.addWidget(self.t1Label, 0, 0)
        paramLayout.addWidget(self.t1Input, 0, 1)
        paramLayout.addWidget(self.t2Label, 1, 0)
        paramLayout.addWidget(self.t2Input, 1, 1)
        self.singleParamGroup.setLayout(paramLayout)
        layout.addWidget(self.singleParamGroup)

        # 多特征模式输入
        self.multiParamGroup = QGroupBox("多特征参数")
        multi_layout = QHBoxLayout()
        self.t1List = QListWidget()
        self.t1List.setSelectionMode(QAbstractItemView.MultiSelection)
        self.t2List = QListWidget()
        self.t2List.setSelectionMode(QAbstractItemView.MultiSelection)
        
        multi_layout.addWidget(QLabel("T1特征集:"))
        multi_layout.addWidget(self.t1List)
        multi_layout.addWidget(QLabel("T2特征集:"))
        multi_layout.addWidget(self.t2List)
        self.multiParamGroup.setLayout(multi_layout)
        self.multiParamGroup.hide()
        layout.addWidget(self.multiParamGroup)

        # 预定义纹理指数
        presetLayout = QHBoxLayout()
        self.addNDTIButton = QPushButton("添加NDTI")
        self.addNDTIButton.clicked.connect(lambda: self.addPresetIndex("NDTI"))
        self.addRDTIButton = QPushButton("添加RDTI")
        self.addRDTIButton.clicked.connect(lambda: self.addPresetIndex("RDTI"))
        
        presetLayout.addWidget(self.addNDTIButton)
        presetLayout.addWidget(self.addRDTIButton)
        layout.addLayout(presetLayout)

        # 自定义公式输入
        customLayout = QVBoxLayout()
        self.formulaInput = QLineEdit()
        self.formulaInput.setPlaceholderText("输入自定义公式（使用T1和T2），示例：T1 - T2")
        self.addCustomButton = QPushButton("添加自定义公式")
        self.addCustomButton.clicked.connect(self.addCustomFormula)
        
        customLayout.addWidget(QLabel("自定义公式:"))
        customLayout.addWidget(self.formulaInput)
        customLayout.addWidget(self.addCustomButton)
        layout.addLayout(customLayout)

        # 指数显示区域
        self.indicesWidget = QWidget()
        self.indicesLayout = QGridLayout(self.indicesWidget)
        self.indicesLayout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.indicesWidget)
        layout.addWidget(scroll)

        # 运行按钮
        self.runButton = QPushButton("开始计算")
        self.runButton.setStyleSheet(
        "QPushButton{font-size:12pt; padding:8px; background:#4CAF50; color:white;}"
        "QPushButton:hover{background:#45a049;}"
        )
        self.runButton.clicked.connect(self.calculateIndices)
        layout.addWidget(self.runButton)

        # 模式切换信号
        self.singleMode.toggled.connect(self.updateUI)
        self.multiMode.toggled.connect(self.updateUI)
        self.fullMode.toggled.connect(self.updateUI)

        self.setLayout(layout)
        self.loadCustomIndices()

    def updateUI(self):
        """根据选择模式更新界面"""
        self.singleParamGroup.setVisible(self.singleMode.isChecked())
        self.multiParamGroup.setVisible(self.multiMode.isChecked())

    def browseCsv(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV files (*.csv)")
        if filename:
            self.csvLineEdit.setText(filename)
            self.csv_path = filename
            self.loadFeatures()

    def loadFeatures(self):
        """加载CSV文件特征列"""
        try:
            df = pd.read_csv(self.csv_path)
            self.all_features = [col for col in df.columns if col not in ['ID', 'FileName']]
            
            # 更新多选列表
            self.t1List.clear()
            self.t2List.clear()
            for feature in self.all_features:
                self.t1List.addItem(feature)
                self.t2List.addItem(feature)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载CSV失败: {str(e)}")

    def addPresetIndex(self, index_type):
        formulas = {
            "NDTI": "(T1 - T2) / ((T1 + T2) + 1e-9)",
            "RDTI": "(T1 - T2) / (np.sqrt(T1 + T2) + 1e-9)"
        }
        self._createIndexWidget(index_type, formulas[index_type])

    def addCustomFormula(self):
        formula = self.formulaInput.text().strip()
        if not formula:
            QMessageBox.warning(self, "错误", "请输入有效公式！")
            return
        
        if 'T1' not in formula or 'T2' not in formula:
            QMessageBox.warning(self, "错误", "公式必须包含T1和T2变量！")
            return
        
        index_name = f"CTI{len(self.textureOptions)+1}"
        self._createIndexWidget(index_name, formula)
        self.formulaInput.clear()

    def _createIndexWidget(self, name, formula):
        container = QWidget()
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        
        cb = QCheckBox(f"{name}: {formula}")
        self.textureOptions[name] = {"formula": formula, "checkbox": cb}
        
        delBtn = QPushButton("删除")
        delBtn.clicked.connect(lambda: self.removeIndex(container, name))
        
        hbox.addWidget(cb)
        hbox.addWidget(delBtn)
        self.indicesLayout.addWidget(container)

    def removeIndex(self, widget, name):
        self.indicesLayout.removeWidget(widget)
        widget.deleteLater()
        del self.textureOptions[name]

    def loadCustomIndices(self):
        if os.path.exists(self.customIndicesFile):
            try:
                with open(self.customIndicesFile, "r") as f:
                    indices = json.load(f)
                for name, formula in indices.items():
                    self._createIndexWidget(name, formula)
            except Exception as e:
                QMessageBox.warning(self, "加载错误", f"无法加载自定义指数: {str(e)}")

    def saveCustomIndices(self):
        indices = {name: data["formula"] for name, data in self.textureOptions.items() 
                 if not name.startswith(("NDTI", "RDTI"))}
        try:
            with open(self.customIndicesFile, "w") as f:
                json.dump(indices, f)
        except Exception as e:
            QMessageBox.warning(self, "保存错误", f"无法保存自定义指数: {str(e)}")

    def calculateIndices(self):
        if not self.csv_path:
            QMessageBox.warning(self, "错误", "请先选择CSV文件！")
            return
        
        try:
            df = pd.read_csv(self.csv_path)
            selected = [name for name, data in self.textureOptions.items() 
                    if data["checkbox"].isChecked()]
            
            if not selected:
                QMessageBox.warning(self, "错误", "请至少选择一个指数！")
                return
            
            # 根据模式获取特征组合
            if self.fullMode.isChecked():
                combinations = list(product(self.all_features, repeat=2))
            elif self.multiMode.isChecked():
                t1_features = [item.text() for item in self.t1List.selectedItems()]
                t2_features = [item.text() for item in self.t2List.selectedItems()]
                combinations = list(product(t1_features, t2_features))
            else:  # 单特征模式
                t1 = self.t1Input.text().strip()
                t2 = self.t2Input.text().strip()
                combinations = [(t1, t2)]

            # 验证特征组合有效性
            valid_combinations = []
            for t1_col, t2_col in combinations:
                if t1_col in df.columns and t2_col in df.columns:
                    valid_combinations.append((t1_col, t2_col))
            
            if not valid_combinations:
                QMessageBox.warning(self, "错误", "没有有效的特征组合！")
                return

            # 遍历每个指数单独保存
            for index in selected:
                index_output_df = df[['ID', 'FileName']].copy() if 'ID' in df.columns else pd.DataFrame()
                formula = self.textureOptions[index]["formula"]
                
                try:
                    for t1_col, t2_col in valid_combinations:
                        T1 = df[t1_col].values.astype(float)
                        T2 = df[t2_col].values.astype(float)
                        
                        values = eval(formula, {"np": np, "T1": T1, "T2": T2})
                        col_name = f"{index}({t1_col},{t2_col})"
                        index_output_df[col_name] = values
                    
                    # 弹出保存对话框
                    save_path, _ = QFileDialog.getSaveFileName(
                        self, 
                        f"保存 {index} 结果", 
                        "", 
                        "CSV文件 (*.csv)"
                    )
                    
                    if save_path:
                        # 自动添加指数名称到文件名
                        base_path, ext = os.path.splitext(save_path)
                        final_path = f"{base_path}_{index}{ext}"
                        index_output_df.to_csv(final_path, index=False)
                        QMessageBox.information(self, "完成", f"{index} 结果已保存至：\n{final_path}")
                        
                except Exception as e:
                    QMessageBox.warning(self, "计算错误", f"{index} 计算失败: {str(e)}")
                    return
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理错误: {str(e)}")

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = CustomTextureIndexTab()
    window.show()
    sys.exit(app.exec_())