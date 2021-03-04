import pickle  # 序列化库
import sys
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication, QComboBox, QFileDialog, QLabel, QMessageBox, QProgressBar, QPushButton, \
    QLineEdit, QVBoxLayout, QWidget, QHBoxLayout


class Node:
    """节点类"""

    def __init__(self, character: int, weight: int):
        """用字符（字节）及其权值（频次）构造节点"""
        self.character = character
        """节点表示的字节"""
        self.weight = weight
        """节点权值（所有叶节点权值之和）"""
        self.left = None
        """左子节点"""
        self.right = None
        """右子节点"""

    @staticmethod
    def merge(left, right):
        """将两个节点合并为新节点"""
        node = Node(0, left.weight + right.weight)
        node.left = left
        node.right = right
        return node

    def is_leaf(self):
        """判断节点是否为叶节点"""
        return self.left is None


class Tree:
    """树类"""

    def __init__(self, root: Node):
        """构造一棵树"""
        self.root = root
        """根节点"""
        self.weight = root.weight
        """根节点的权值"""

    @staticmethod
    def merge(left, right):
        """将两棵树合并为新树"""
        return Tree(Node.merge(left.root, right.root))


class HuffmanTree(Tree):
    """Huffman树类"""

    def __init__(self, dic: dict):
        """以字符（字节）及对应的权值（频次）构造Huffman树"""
        self.codes = {}
        """字符（字节）及对应的Huffman编码"""
        # 以每个字符及其频次构建一颗无子节点的树，加入树林
        trees = [Tree(Node(i, dic[i])) for i in dic]
        # 对树林以权值升序排列，从而减少后续插入的操作次数
        trees.sort(key=lambda x: x.weight)
        # 合并权值最小的两颗树，直到只剩下一棵树
        while len(trees) > 1:
            tree = Tree.merge(trees[0], trees[1])
            trees.pop(0)
            trees.pop(0)
            HuffmanTree.__add_tree(trees, tree)
        super().__init__(trees[0].root)
        # 如果只有一个节点，即只有一种字节，则将其编码为“0”
        if self.root.is_leaf():
            self.codes[self.root.character] = '0'
        else:
            self.__generate_code(self.root, '')  # 递归编码

    @staticmethod
    def __add_tree(trees, tree: Tree):
        """将树插入树林"""
        i = 0
        while i < len(trees):
            if tree.weight <= trees[i].weight:
                break
            i += 1
        trees.insert(i, tree)

    def __generate_code(self, root: Node, code: str):
        """递归生成Huffman编码"""
        # 如果是叶节点，则编码就是code
        if root.is_leaf():
            self.codes[root.character] = code
        # 如果不是叶节点，分别以code||0和code||1为前缀生成子节点的编码
        else:
            self.__generate_code(root.left, code + '0')
            self.__generate_code(root.right, code + '1')


class Compress:
    """压缩和解压类"""

    @staticmethod
    def compress(infile, outfile, process_bar):
        """压缩文件"""
        dic, length = Compress.count(infile)  # 统计字符频率和文件长度
        pickle.dump(length, outfile)  # 将文件长度写入文件头
        if length == 0:
            return
        # 构造Huffman树，并写入文件头
        tree = HuffmanTree(dic)
        pickle.dump(tree.root, outfile)
        infile.seek(0)
        buffer = ''  # 设置缓冲区，达到1字节后写入
        data = infile.read(16)
        complete = 0
        while len(data) != 0:
            for i in data:
                buffer += tree.codes[i]
            while len(buffer) >= 8:
                outfile.write(bytes([int(buffer[0:8], 2)]))
                buffer = buffer[8:]
            complete += len(data)
            process_bar.setValue(complete * 100 // length)  # 修改进度
            data = infile.read(16)
        # 最后不足8位填充“0”
        if len(buffer) > 0:
            outfile.write(bytes([int(buffer + '0' * (8 - len(buffer)), 2)]))

    @staticmethod
    def count(infile):
        """统计字符频率和文件长度"""
        dic = {}
        data = infile.read(16)
        length = 0  # 文件总字节数
        # 统计字符的频次
        while len(data) > 0:
            length += len(data)
            for i in data:
                dic[i] = dic.get(i, 0) + 1
            data = infile.read(16)
        return dic, length

    @staticmethod
    def decompress(infile, outfile, process_bar):
        """解压文件"""
        length = pickle.load(infile)  # 读取原文件长度
        if length == 0:
            process_bar.setValue(100)  # 解压完成
            return
        root = pickle.load(infile)  # 重建Huffman树
        buffer = ''  # 缓冲区，存放读取但未解压的数据
        data = infile.read(4)
        complete = 0
        while complete < length:
            if len(buffer) < 32 and len(data) > 0:
                for i in data:
                    buffer += "{:b}".format(i).zfill(8)
                data = infile.read(4)
            # 解压缓冲区的第一个字符
            else:
                reduce = Compress.__write_byte(buffer, root, outfile)
                complete += 1
                process_bar.setValue(complete * 100 // length)  # 修改进度
                buffer = buffer[reduce:]

    @staticmethod
    def __write_byte(buffer: str, root: Node, outfile):
        """解压并写入缓冲区的第一个字符，返回解压的数据长度"""
        node = root
        n = 0  # 该字符包含的比特数
        # 若根节点无子节点，即只有一种字符，写入该字符
        if node.is_leaf():
            n += 1
        else:
            while not node.is_leaf():  # 节点有子节点，表示该节点无编码
                # 下一位为0，则是左子树上的编码，否则为右子树上的编码
                node = node.left if buffer[n] == '0' else node.right
                n += 1
        outfile.write(bytes([node.character]))  # 此时已找到叶节点，写入对应的原字符
        return n


class HWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(800, 500)
        self.setWindowTitle('Huffman')
        self.setWindowIcon(QIcon('source/icon.png'))

        # 顶部，包括Python和QT的logo
        top_hbox = QHBoxLayout()
        python_logo = QLabel()
        python_logo.setPixmap(QPixmap('source/python-logo.png'))
        python_logo.setMaximumHeight(100)
        qt_logo = QLabel()
        qt_logo.setPixmap(QPixmap('source/qt-logo.png'))
        qt_logo.setMaximumHeight(100)
        top_hbox.addWidget(python_logo)
        top_hbox.addStretch(1)
        top_hbox.addWidget(qt_logo)

        # 选择输入文件
        in_hbox = QHBoxLayout()
        in_label = QLabel()
        in_label.setText('输入文件')
        self.in_textedit = QLineEdit()
        self.in_textedit.setPlaceholderText('点击按钮或输入路径')
        in_button = QPushButton('选择文件')
        # 点击开始按钮时弹出文件选择对话框，并将选择的文件路径显示在文本框内
        in_button.clicked.connect(self.__select_in)
        in_hbox.addWidget(in_label)
        in_hbox.addWidget(self.in_textedit)
        in_hbox.addWidget(in_button)

        # 选择输出文件
        out_hbox = QHBoxLayout()
        out_label = QLabel()
        out_label.setText('输出文件')
        self.out_textedit = QLineEdit()
        self.out_textedit.setPlaceholderText('点击按钮或输入路径')
        out_button = QPushButton('选择文件')
        out_button.clicked.connect(self.__select_out)
        out_hbox.addWidget(out_label)
        out_hbox.addWidget(self.out_textedit)
        out_hbox.addWidget(out_button)

        # 选择操作及开始按钮
        option_hbox = QHBoxLayout()
        option_label = QLabel()
        option_label.setText('选择操作')
        self.option_menu = QComboBox()
        self.option_menu.addItems(['压缩', '解压'])
        self.start_button = QPushButton('开始', self)
        self.start_button.clicked.connect(self.__start)
        option_hbox.addWidget(option_label)
        option_hbox.addWidget(self.option_menu)
        option_hbox.addStretch(1)
        option_hbox.addWidget(self.start_button)

        # 进度条
        process_hbox = QHBoxLayout()
        self.process_bar = QProgressBar()
        self.process_bar.setValue(0)
        process_hbox.addWidget(self.process_bar)

        # 采用垂直箱式布局，各部分又使用水平箱式布局
        vbox = QVBoxLayout()
        vbox.addLayout(top_hbox)
        vbox.addStretch(2)
        vbox.addLayout(in_hbox)
        vbox.addStretch(1)
        vbox.addLayout(out_hbox)
        vbox.addStretch(1)
        vbox.addLayout(option_hbox)
        vbox.addStretch(1)
        vbox.addLayout(process_hbox)
        vbox.addStretch(2)
        self.setLayout(vbox)

        self.show()

    def __start(self):
        """"点击开始按钮后进行的操作"""
        self.start_button.setEnabled(False)
        self.process_bar.setValue(0)
        option = self.option_menu.currentText()
        try:
            with open(self.in_textedit.text(), 'rb') as infile, open(self.out_textedit.text(), 'wb') as outfile:
                if option == '压缩':
                    Compress.compress(infile, outfile, self.process_bar)
                else:
                    Compress.decompress(infile, outfile, self.process_bar)
        # 出错时弹窗提示
        except pickle.UnpicklingError:
            QMessageBox.critical(self, '错误', '压缩文件错误，请检查', QMessageBox.Ok)
        except FileNotFoundError:
            QMessageBox.critical(self, '错误', '文件路径有误，请检查', QMessageBox.Ok)
        except Exception as e:
            QMessageBox.critical(self, '错误', repr(e), QMessageBox.Ok)
        else:
            self.process_bar.setValue(100)
            QMessageBox.information(self, f'{option}完成', f'{option}已完成，{option}文件保存在{outfile.name}',
                                    QMessageBox.Ok)  # 完成时弹窗提示
        self.start_button.setEnabled(True)

    def __select_in(self):
        """输入文件选择对话框"""
        self.in_textedit.setText(
            QFileDialog.getOpenFileName(self, '选择输入文件')[0])

    def __select_out(self):
        """输出文件选择对话框"""
        self.out_textedit.setText(
            QFileDialog.getOpenFileName(self, '选择输入文件')[0])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = HWidget()
    sys.exit(app.exec_())
