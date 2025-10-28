#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双窗口文件浏览器

一个模仿macOS Finder的双窗口文件浏览器应用，支持文件浏览、导航和基本操作。
"""

import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
from pathlib import Path

# 尝试导入paramiko库用于SFTP功能
try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False
    print("警告: 未安装paramiko库，SFTP功能将不可用。请运行 'pip install paramiko' 安装")

class Sidebar(tk.Frame):
    """侧边栏组件，显示硬盘设备和重要目录"""
    
    def __init__(self, parent, on_path_select=None):
        super().__init__(parent)
        self.on_path_select = on_path_select
        self.configure(bg='#f2f2f7')
        
        # 创建图标
        self.create_icons()
        
        # 创建标题
        self.title_label = tk.Label(self, text="设备和位置", font=('Arial', 10, 'bold'), bg='#f2f2f7')
        self.title_label.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建滚动条和树状视图
        self.frame = tk.Frame(self, bg='#f2f2f7')
        self.frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.vscroll = ttk.Scrollbar(self.frame)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建树状视图用于显示设备和目录
        # 设置show参数包含图标列
        self.tree = ttk.Treeview(self.frame, yscrollcommand=self.vscroll.set, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.vscroll.config(command=self.tree.yview)
        
        # 设置样式
        self.tree.column('#0', width=150, minwidth=150)
        
        # 绑定事件
        self.tree.bind('<Double-1>', self.on_item_double_click)
        
        # 初始化内容
        self.refresh_content()
        
        # 启动自动刷新定时器（每3秒刷新一次）
        self.start_auto_refresh()
    
    def create_icons(self):
        """创建侧边栏使用的图标"""
        # 使用Unicode符号作为图标，而不是依赖Tkinter的bitmap
        self.symbol_mapping = {
            'devices_folder': '📁',           # 设备文件夹图标
            'volumes': '💾',                  # 卷/设备图标
            'important_folder': '📂',         # 重要目录文件夹图标
            'home': '🏠',                     # 主文件夹图标
            'desktop': '🖥️',                  # 桌面图标
            'documents': '📄',                # 文档图标
            'downloads': '⬇️',                # 下载图标
            'music': '🎵',                    # 音乐图标
            'pictures': '🖼️',                 # 照片图标
            'movies': '🎬'                    # 电影图标
        }
        
        # 初始化图标字典为空字符串，因为我们将在文本前添加符号
        self.icons = {}
        for key in self.symbol_mapping.keys():
            self.icons[key] = ''
    
    def start_auto_refresh(self):
        """启动自动刷新定时器"""
        def refresh_device_list():
            # 只检查设备变化，不刷新重要目录
            self.update_devices()
            # 继续定时刷新
            self.after(3000, refresh_device_list)
        
        # 启动第一个刷新
        self.after(3000, refresh_device_list)
    
    def update_devices(self):
        """更新设备列表，不影响重要目录"""
        volumes_dir = '/Volumes'
        if not os.path.exists(volumes_dir):
            return
        
        try:
            # 获取当前挂载的卷
            current_volumes = os.listdir(volumes_dir)
            current_volumes = [v for v in current_volumes if not v.startswith('.')]
            
            # 获取设备节点下的所有子项
            devices_node = None
            existing_volumes = set()
            
            # 查找设备节点（考虑带有符号前缀的文本）
            for item in self.tree.get_children():
                text = self.tree.item(item, 'text')
                # 检查文本是否包含'设备'，不管前缀是什么
                if '设备' in text:
                    devices_node = item
                    break
            
            # 如果没有设备节点，创建一个
            if not devices_node:
                devices_text = f"{self.symbol_mapping.get('devices_folder', '')} 设备"
                devices_node = self.tree.insert('', tk.END, text=devices_text, open=True)
            
            # 获取现有设备列表
            for child in self.tree.get_children(devices_node):
                # 移除符号前缀，只保留卷名
                volume_text = self.tree.item(child, 'text')
                # 假设格式为 "符号 名称"，我们需要提取名称部分
                if ' ' in volume_text:
                    volume_name = volume_text.split(' ', 1)[1]
                else:
                    volume_name = volume_text
                existing_volumes.add(volume_name)
            
            # 添加新设备，使用符号前缀
            new_volumes = set(current_volumes) - existing_volumes
            for volume in new_volumes:
                volume_path = os.path.join(volumes_dir, volume)
                # 添加符号前缀
                volume_text = f"{self.symbol_mapping.get('volumes', '')} {volume}"
                self.tree.insert(devices_node, tk.END, text=volume_text, tags=('device',), values=(volume_path,))
            
            # 移除已卸载的设备
            removed_volumes = existing_volumes - set(current_volumes)
            for child in list(self.tree.get_children(devices_node)):
                # 移除符号前缀，只保留卷名
                volume_text = self.tree.item(child, 'text')
                if ' ' in volume_text:
                    volume_name = volume_text.split(' ', 1)[1]
                else:
                    volume_name = volume_text
                
                if volume_name in removed_volumes:
                    self.tree.delete(child)
                    
        except Exception as e:
            print(f"更新设备列表时出错: {e}")
    
    def refresh_content(self):
        """刷新侧边栏内容"""
        # 清空现有内容
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 获取并显示硬盘设备
        self.add_devices()
        
        # 获取并显示重要目录
        self.add_important_directories()
    
    def add_devices(self):
        """添加硬盘设备"""
        # 在macOS上，设备挂载在/Volumes目录
        volumes_dir = '/Volumes'
        if os.path.exists(volumes_dir):
            # 创建设备父节点，使用符号前缀
            devices_text = f"{self.symbol_mapping.get('devices_folder', '')} 设备"
            devices_node = self.tree.insert('', tk.END, text=devices_text, open=True)
            
            try:
                # 获取所有挂载的卷
                volumes = os.listdir(volumes_dir)
                for volume in volumes:
                    # 跳过隐藏文件和文件夹
                    if volume.startswith('.'):
                        continue
                    
                    # 添加卷到树状视图，使用符号前缀
                    volume_path = os.path.join(volumes_dir, volume)
                    volume_text = f"{self.symbol_mapping.get('volumes', '')} {volume}"
                    self.tree.insert(devices_node, tk.END, text=volume_text, tags=('device',), 
                                    values=(volume_path,))
            except Exception as e:
                print(f"获取设备信息时出错: {e}")
    
    def add_important_directories(self):
        """添加重要目录"""
        # 创建重要目录父节点，使用符号前缀
        dirs_text = f"{self.symbol_mapping.get('important_folder', '')} 重要目录"
        dirs_node = self.tree.insert('', tk.END, text=dirs_text, open=True)
        
        # 主目录下的重要文件夹，包含对应的图标类型
        important_dirs = {
            '主文件夹': (os.path.expanduser('~'), 'home'),
            '桌面': (os.path.expanduser('~/Desktop'), 'desktop'),
            '文档': (os.path.expanduser('~/Documents'), 'documents'),
            '下载': (os.path.expanduser('~/Downloads'), 'downloads'),
            '音乐': (os.path.expanduser('~/Music'), 'music'),
            '照片': (os.path.expanduser('~/Pictures'), 'pictures'),
            '电影': (os.path.expanduser('~/Movies'), 'movies')
        }
        
        # 添加每个重要目录，使用对应的符号前缀
        for name, (path, icon_type) in important_dirs.items():
            if os.path.exists(path):
                # 在名称前添加符号
                display_text = f"{self.symbol_mapping.get(icon_type, '')} {name}"
                self.tree.insert(dirs_node, tk.END, text=display_text, tags=('directory',), values=(path,))
    
    def on_item_double_click(self, event):
        """双击项目处理"""
        item = self.tree.selection()[0]
        values = self.tree.item(item, 'values')
        
        # 如果有路径值，调用回调函数
        if values and self.on_path_select:
            self.on_path_select(values[0])

class FileBrowser(tk.Frame):
    """文件浏览器组件"""
    
    def __init__(self, parent, on_path_change=None, on_file_select=None, on_folder_select=None):
        super().__init__(parent)
        self.on_path_change = on_path_change
        self.on_file_select = on_file_select
        self.on_folder_select = on_folder_select
        self.is_active = False  # 窗口激活状态标志
        self.master = parent  # 保存对父窗口的引用
        
        # 设置主题和样式
        self.style = ttk.Style()
        # macOS风格设置
        self.configure(bg='#f2f2f7')
        self.style.configure('TButton', background='#f2f2f7', foreground='#000000')
        self.style.configure('TCombobox', background='#ffffff', foreground='#000000')
        self.style.configure('Treeview', background='#ffffff', foreground='#000000',
                            fieldbackground='#ffffff', rowheight=22)
        self.style.configure('Treeview.Heading', background='#f2f2f7', foreground='#000000')
        
        # 创建导航栏
        self.create_navbar()
        
        # 创建文件列表视图
        self.create_file_list()
        
        # 创建状态栏
        self.create_statusbar()
        
        # 设置布局
        self.navbar.pack(fill=tk.X, padx=5, pady=5)
        self.file_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.statusbar.pack(fill=tk.X, padx=5, pady=5)
        
        # 当前路径
        self.current_path = os.path.expanduser('~')
        
        # 隐藏文件显示标志
        self.show_hidden = False
        
        # 绑定事件
        self.bind_events()
        
        # 初始化显示
        self.refresh_file_list()
        
    def create_navbar(self):
        """创建导航栏"""
        self.navbar = tk.Frame(self, bg='#f2f2f7')
        
        # 返回按钮
        self.back_btn = ttk.Button(self.navbar, text='←', width=3, command=self.go_back)
        self.back_btn.pack(side=tk.LEFT, padx=2)
        
        # 前进按钮
        self.forward_btn = ttk.Button(self.navbar, text='→', width=3, command=self.go_forward)
        self.forward_btn.pack(side=tk.LEFT, padx=2)
        
        # 向上按钮
        self.up_btn = ttk.Button(self.navbar, text='↑', width=3, command=self.go_up)
        self.up_btn.pack(side=tk.LEFT, padx=2)
        
        # 路径输入框
        self.path_var = tk.StringVar()
        self.path_entry = ttk.Combobox(self.navbar, textvariable=self.path_var, width=50,
                                      state='readonly')
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.bind('<Return>', lambda e: self.navigate_to_path())
        
        # 刷新按钮
        self.refresh_btn = ttk.Button(self.navbar, text='刷新', command=self.refresh_file_list)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)
    
    def create_file_list(self):
        """创建文件列表视图"""
        # 创建带滚动条的树状视图
        self.file_frame = tk.Frame(self)
        
        # 垂直滚动条
        self.vscroll = ttk.Scrollbar(self.file_frame, orient=tk.VERTICAL)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 水平滚动条
        self.hscroll = ttk.Scrollbar(self.file_frame, orient=tk.HORIZONTAL)
        self.hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 树状视图 - 设置为支持多选
        self.tree = ttk.Treeview(self.file_frame, columns=('name', 'type', 'size', 'modified'),
                               show='headings', yscrollcommand=self.vscroll.set,
                               xscrollcommand=self.hscroll.set, selectmode='extended')
        
        # 设置列
        self.tree.heading('name', text='名称', command=lambda: self.sort_by_column('name'))
        self.tree.heading('type', text='类型', command=lambda: self.sort_by_column('type'))
        self.tree.heading('size', text='大小', command=lambda: self.sort_by_column('size'))
        self.tree.heading('modified', text='修改日期', command=lambda: self.sort_by_column('modified'))
        
        # 设置列宽
        self.tree.column('name', width=250, minwidth=150)
        self.tree.column('type', width=100, minwidth=80)
        self.tree.column('size', width=80, minwidth=60, anchor=tk.E)
        self.tree.column('modified', width=150, minwidth=120)
        
        # 创建标签用于颜色区分
        self.tree.tag_configure('folder', foreground='#0066cc')  # 文件夹使用蓝色
        self.tree.tag_configure('file', foreground='#000000')    # 文件使用黑色
        
        # 连接滚动条
        self.vscroll.config(command=self.tree.yview)
        self.hscroll.config(command=self.tree.xview)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.file_list = self.file_frame
    
    def create_statusbar(self):
        """创建状态栏"""
        self.statusbar = tk.Frame(self, height=20, bg='#f2f2f7', bd=1, relief=tk.SUNKEN)
        self.status_var = tk.StringVar()
        self.status_var.set('就绪')
        self.status_label = tk.Label(self.statusbar, textvariable=self.status_var, 
                                    bg='#f2f2f7', font=('Helvetica', 10), anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=5, pady=2)
    
    def bind_events(self):
        """绑定事件"""
        # 双击打开文件或文件夹
        self.tree.bind('<Double-1>', self.on_double_click)
        
        # 单击选择文件
        self.tree.bind('<ButtonRelease-1>', self.on_single_click)
        
        # 支持拖放
        self.tree.bind('<ButtonPress-1>', self.on_drag_start)
        self.tree.bind('<B1-Motion>', self.on_drag_motion)
        self.tree.bind('<ButtonRelease-1>', self.on_drag_end)
        
        # 支持键盘操作
        self.tree.bind('<Return>', self.on_enter_press)
        self.tree.bind('<Delete>', self.on_delete_press)
        self.tree.bind('<F5>', lambda e: self.refresh_file_list())
        
        # 绑定窗口点击事件，用于激活窗口 - 确保点击任何区域都能激活窗口
        # 为所有主要组件绑定点击事件
        self.navbar.bind('<Button-1>', self.on_frame_click)
        self.file_frame.bind('<Button-1>', self.on_frame_click)
        self.statusbar.bind('<Button-1>', self.on_frame_click)
        
        # 为Treeview绑定点击事件，但让它先处理自己的点击逻辑，然后再激活窗口
        self.tree.bind('<Button-1>', self.on_tree_click)
        
        # 为所有按钮绑定点击事件，确保点击按钮时也能激活窗口
        for child in self.navbar.winfo_children():
            if isinstance(child, ttk.Button):
                child.bind('<Button-1>', lambda e: self.on_frame_click(e))
        
        # 为路径输入框绑定点击事件
        if hasattr(self, 'path_entry'):
            self.path_entry.bind('<Button-1>', lambda e: self.on_frame_click(e))
            
        # 为整个框架绑定点击事件，确保点击任何空白区域也能激活窗口
        self.bind('<Button-1>', self.on_frame_click)
        
    def on_frame_click(self, event):
        """窗口点击事件，激活当前窗口"""
        # 通知主窗口激活此浏览器
        if hasattr(self, 'app'):
            self.app.set_active_browser(self)
        else:
            # 尝试通过winfo_toplevel()获取顶层窗口，然后访问finder_app属性
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, 'finder_app'):
                toplevel.finder_app.set_active_browser(self)
            # 也尝试从父窗口获取
            elif hasattr(self.master, 'finder_app'):
                self.master.finder_app.set_active_browser(self)
        # 不需要阻止事件传播，这样点击按钮等组件时既可以激活窗口，又能执行组件功能
        return
        
    def on_tree_click(self, event):
        """Treeview点击事件处理"""
        # 先执行正常的Treeview点击逻辑（选择项目等）
        # 由于我们没有在这里实现选择逻辑，它会使用默认行为
        
        # 然后激活窗口 - 通过app属性访问主应用程序
        if hasattr(self, 'app'):
            self.app.set_active_browser(self)
        else:
            # 尝试通过winfo_toplevel()获取顶层窗口，然后访问finder_app属性
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, 'finder_app'):
                toplevel.finder_app.set_active_browser(self)
        
    def set_active(self, active=True):
        """设置窗口激活状态并添加颜色标识"""
        self.is_active = active
        
        # 设置不同的背景色来区分激活状态
        if active:
            # 激活状态：更亮的背景色
            self.configure(bg='#e3f2fd')  # 浅蓝色背景
            self.navbar.configure(bg='#e3f2fd')
            self.file_frame.configure(bg='#e3f2fd')
            self.statusbar.configure(bg='#e3f2fd')
            
            # 添加边框高亮
            self.config(bd=2, relief=tk.RAISED)
            
            # 更改样式
            self.style.configure('TButton', background='#e3f2fd')
            self.style.configure('Treeview.Heading', background='#bbdefb')  # 更亮的表头背景
        else:
            # 非激活状态：默认背景色
            self.configure(bg='#f2f2f7')
            self.navbar.configure(bg='#f2f2f7')
            self.file_frame.configure(bg='#f2f2f7')
            self.statusbar.configure(bg='#f2f2f7')
            
            # 移除边框高亮
            self.config(bd=0, relief=tk.FLAT)
            
            # 恢复默认样式
            self.style.configure('TButton', background='#f2f2f7')
            self.style.configure('Treeview.Heading', background='#f2f2f7')
    
    def on_double_click(self, event):
        """双击事件处理"""
        try:
            # 先激活窗口
            if hasattr(self, 'app'):
                self.app.set_active_browser(self)
            else:
                # 尝试通过winfo_toplevel()获取顶层窗口，然后访问finder_app属性
                toplevel = self.winfo_toplevel()
                if hasattr(toplevel, 'finder_app'):
                    toplevel.finder_app.set_active_browser(self)
            
            # 然后处理双击操作
            item = self.tree.identify_row(event.y)
            if item:
                name = self.tree.item(item, 'values')[0]
                # 如果是文件夹，移除[]括号
                if name.startswith('[') and name.endswith(']'):
                    name = name[1:-1]
                
                # 根据模式构建路径
                if hasattr(self, 'is_sftp') and self.is_sftp:
                    path = self.sftp_fs.join(self.current_path, name)
                else:
                    path = os.path.join(self.current_path, name)
                
                # 判断是目录还是文件
                if hasattr(self, 'is_sftp') and self.is_sftp:
                    if self.sftp_fs.isdir(path):
                        # 进入文件夹
                        self.navigate_to(path)
                    else:
                        # 打开文件
                        self.open_file(path)
                else:
                    if os.path.isdir(path):
                        # 进入文件夹
                        self.navigate_to(path)
                    else:
                        # 打开文件
                        self.open_file(path)
        except Exception as e:
            # 添加错误处理
            self.status_var.set(f"双击操作失败: {str(e)}")
            # 使用after来避免在事件处理中显示messagebox可能导致的问题
            if hasattr(self, 'master'):
                self.master.after(0, messagebox.showerror, "错误", f"双击操作失败: {str(e)}")
    
    def on_single_click(self, event):
        """单击事件处理"""
        # 先激活窗口
        if hasattr(self, 'app'):
            self.app.set_active_browser(self)
        else:
            # 尝试通过winfo_toplevel()获取顶层窗口，然后访问finder_app属性
            toplevel = self.winfo_toplevel()
            if hasattr(toplevel, 'finder_app'):
                toplevel.finder_app.set_active_browser(self)
        
        # 然后处理文件选择
        item = self.tree.identify_row(event.y)
        if item:
            name = self.tree.item(item, 'values')[0]
            # 如果是文件夹，移除[]括号
            if name.startswith('[') and name.endswith(']'):
                name = name[1:-1]
            path = os.path.join(self.current_path, name)
            
            if os.path.isdir(path) and self.on_folder_select:
                self.on_folder_select(path)
            elif self.on_file_select:
                self.on_file_select(path)
    
    def on_enter_press(self, event):
        """回车事件处理"""
        try:
            selected = self.tree.selection()
            if selected:
                name = self.tree.item(selected[0], 'values')[0]
                # 如果是文件夹，移除[]括号
                if name.startswith('[') and name.endswith(']'):
                    name = name[1:-1]
                    
                # 根据模式构建路径
                if hasattr(self, 'is_sftp') and self.is_sftp:
                    path = self.sftp_fs.join(self.current_path, name)
                else:
                    path = os.path.join(self.current_path, name)
                
                # 判断是否为目录并导航
                if hasattr(self, 'is_sftp') and self.is_sftp:
                    if self.sftp_fs.isdir(path):
                        self.navigate_to(path)
                    else:
                        self.open_file(path)
                else:
                    if os.path.isdir(path):
                        self.navigate_to(path)
                    else:
                        self.open_file(path)
        except Exception as e:
            self.status_var.set(f"操作失败: {str(e)}")
    
    def on_delete_press(self, event):
        """删除事件处理，支持删除非空目录"""
        selected = self.tree.selection()
        if selected:
            display_name = self.tree.item(selected[0], 'values')[0]
            # 如果是文件夹，移除[]括号
            name = display_name
            if name.startswith('[') and name.endswith(']'):
                name = name[1:-1]
            path = os.path.join(self.current_path, name)
            
            # 判断是否为非空目录
            is_non_empty_dir = os.path.isdir(path) and len(os.listdir(path)) > 0
            
            # 根据是否为非空目录显示不同的确认消息
            if is_non_empty_dir:
                confirm_msg = f"确定要删除目录 '{display_name}' 及其所有内容吗？此操作不可撤销！"
            else:
                confirm_msg = f"确定要删除 {display_name} 吗？"
            
            if messagebox.askyesno('确认删除', confirm_msg):
                try:
                    if os.path.isdir(path):
                        # 使用shutil.rmtree删除目录及其所有内容
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    self.refresh_file_list()
                except Exception as e:
                    messagebox.showerror('删除失败', str(e))
    
    def on_drag_start(self, event):
        """开始拖拽"""
        item = self.tree.identify_row(event.y)
        if item:
            self.drag_item = item
            self.drag_start_x = event.x
            self.drag_start_y = event.y
    
    def on_drag_motion(self, event):
        """拖拽中"""
        # 简单的拖拽效果
        pass
    
    def on_drag_end(self, event):
        """结束拖拽"""
        # 这里可以实现文件拖拽功能
        self.drag_item = None
    
    def navigate_to(self, path):
        """导航到指定路径"""
        try:
            # 检查是否为SFTP模式
            if hasattr(self, 'is_sftp') and self.is_sftp:
                # SFTP模式下直接使用SFTP的导航方法
                # 这里我们通过app找到原始的_sftp_navigate_to方法
                if hasattr(self, 'app') and hasattr(self.app, '_sftp_navigate_to'):
                    self.app._sftp_navigate_to(self, self.sftp_fs, path)
                else:
                    # 如果无法访问app，尝试直接处理
                    if self.sftp_fs.exists(path) and self.sftp_fs.isdir(path):
                        # 保存历史记录
                        if not hasattr(self, 'history'):
                            self.history = []
                            self.history_index = -1
                        
                        # 如果当前不在历史记录末尾，清除后面的记录
                        if self.history_index < len(self.history) - 1:
                            self.history = self.history[:self.history_index + 1]
                        
                        # 添加当前路径到历史记录
                        if self.current_path != path:
                            self.history.append(self.current_path)
                            self.history_index += 1
                        
                        # 更新当前路径
                        self.current_path = path
                        self.refresh_file_list()
                        
                        # 启用/禁用前进后退按钮
                        self.back_btn['state'] = 'normal' if self.history_index >= 0 else 'disabled'
                        self.forward_btn['state'] = 'normal' if self.history_index < len(self.history) - 1 else 'disabled'
                        
                        # 通知父窗口路径变化
                        if self.on_path_change:
                            self.on_path_change(path)
                    else:
                        self.status_var.set(f"导航错误: 路径不存在或不是目录")
            else:
                # 本地模式
                if os.path.isdir(path):
                    # 保存历史记录
                    if not hasattr(self, 'history'):
                        self.history = []
                        self.history_index = -1
                    
                    # 如果当前不在历史记录末尾，清除后面的记录
                    if self.history_index < len(self.history) - 1:
                        self.history = self.history[:self.history_index + 1]
                    
                    # 添加当前路径到历史记录
                    if hasattr(self, 'current_path') and self.current_path != path:
                        self.history.append(self.current_path)
                        self.history_index += 1
                    
                    # 更新当前路径
                    self.current_path = path
                    self.refresh_file_list()
                    
                    # 启用/禁用前进后退按钮
                    self.back_btn['state'] = 'normal' if self.history_index >= 0 else 'disabled'
                    self.forward_btn['state'] = 'normal' if self.history_index < len(self.history) - 1 else 'disabled'
                    
                    # 通知父窗口路径变化
                    if self.on_path_change:
                        self.on_path_change(path)
        except Exception as e:
            # 添加错误处理
            self.status_var.set(f"导航失败: {str(e)}")
    
    def navigate_to_path(self):
        """根据路径输入导航"""
        path = self.path_var.get()
        if os.path.isdir(path):
            self.navigate_to(path)
    
    def go_back(self):
        """后退"""
        try:
            if hasattr(self, 'history') and self.history_index >= 0:
                path = self.history[self.history_index]
                self.history_index -= 1
                
                # 使用navigate_to而不是直接设置，以确保SFTP模式下也能正确工作
                self.navigate_to(path)
                
                self.back_btn['state'] = 'normal' if self.history_index >= 0 else 'disabled'
                self.forward_btn['state'] = 'normal'
        except Exception as e:
            # 添加错误处理
            self.status_var.set(f"后退导航失败: {str(e)}")
    
    def go_forward(self):
        """前进"""
        try:
            if hasattr(self, 'history') and self.history_index < len(self.history) - 1:
                self.history_index += 1
                path = self.history[self.history_index]
                
                # 使用navigate_to而不是直接设置，以确保SFTP模式下也能正确工作
                self.navigate_to(path)
                
                self.back_btn['state'] = 'normal'
                self.forward_btn['state'] = 'normal' if self.history_index < len(self.history) - 1 else 'disabled'
        except Exception as e:
            # 添加错误处理
            self.status_var.set(f"前进导航失败: {str(e)}")
    
    def go_up(self):
        """向上一级"""
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self.navigate_to(parent)
    
    def refresh_file_list(self):
        """刷新文件列表"""
        # 清空当前列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 更新路径显示
        self.path_var.set(self.current_path)
        
        try:
            # 获取文件列表
            if self.show_hidden:
                # 显示隐藏文件（以.开头的文件）
                items = [item for item in os.listdir(self.current_path)]
            else:
                # 不显示隐藏文件
                items = [item for item in os.listdir(self.current_path) if not item.startswith('.')]
            
            # 分离文件夹和文件
            folders = []
            files = []
            
            for item in items:
                path = os.path.join(self.current_path, item)
                if os.path.isdir(path):
                    folders.append(item)
                else:
                    files.append(item)
            
            # 排序
            folders.sort()
            files.sort()
            
            # 添加到视图
            for folder in folders:
                path = os.path.join(self.current_path, folder)
                try:
                    stat_info = os.stat(path)
                    size = ""
                    modified = time.ctime(stat_info.st_mtime)
                    # 在文件夹名称两边添加[]，并应用folder标签
                    self.tree.insert('', tk.END, values=(f'[{folder}]', '文件夹', size, modified), tags=('folder',))
                except Exception:
                    self.tree.insert('', tk.END, values=(f'[{folder}]', '文件夹', '', ''), tags=('folder',))
            
            for file in files:
                path = os.path.join(self.current_path, file)
                try:
                    stat_info = os.stat(path)
                    size = self.format_size(stat_info.st_size)
                    modified = time.ctime(stat_info.st_mtime)
                    # 获取文件类型
                    file_type = self.get_file_type(file)
                    self.tree.insert('', tk.END, values=(file, file_type, size, modified), tags=('file',))
                except Exception:
                    self.tree.insert('', tk.END, values=(file, '', '', ''), tags=('file',))
            
            # 更新状态栏
            total_items = len(folders) + len(files)
            hidden_status = "(显示隐藏文件)" if self.show_hidden else ""
            self.status_var.set(f'{total_items} 个项目 {hidden_status}')
            
        except Exception as e:
            self.status_var.set(f'错误: {str(e)}')
    
    def format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def get_file_type(self, filename):
        """获取文件类型"""
        ext = os.path.splitext(filename)[1].lower()
        
        # 常见文件类型
        file_types = {
            '.txt': '文本文件',
            '.doc': 'Word文档',
            '.docx': 'Word文档',
            '.pdf': 'PDF文档',
            '.jpg': 'JPEG图像',
            '.jpeg': 'JPEG图像',
            '.png': 'PNG图像',
            '.gif': 'GIF图像',
            '.mp3': '音频文件',
            '.mp4': '视频文件',
            '.mov': '视频文件',
            '.zip': '压缩文件',
            '.rar': '压缩文件',
            '.py': 'Python文件',
            '.html': 'HTML文件',
            '.css': 'CSS文件',
            '.js': 'JavaScript文件',
            '.json': 'JSON文件',
            '.xml': 'XML文件',
            '.csv': 'CSV文件',
            '.xlsx': 'Excel文件',
            '.pptx': 'PowerPoint文件',
            '.dmg': '磁盘镜像',
            '.app': '应用程序',
        }
        
        return file_types.get(ext, '文件')
    
    def sort_by_column(self, column):
        """按列排序文件列表"""
        # 获取当前所有项目
        items = list(self.tree.get_children())
        if not items:
            return
        
        # 获取当前排序状态
        current_heading = self.tree.heading(column)
        current_text = current_heading['text']
        
        # 判断当前排序方向并切换
        if current_text.endswith(' ▼'):
            # 当前是降序，切换到升序
            reverse = False
            new_text = current_text.replace(' ▼', ' ▲')
        elif current_text.endswith(' ▲'):
            # 当前是升序，切换到降序
            reverse = True
            new_text = current_text.replace(' ▲', ' ▼')
        else:
            # 首次点击，默认升序
            reverse = False
            new_text = current_text + ' ▲'
        
        # 更新表头文本
        self.tree.heading(column, text=new_text)
        
        # 重置其他列的表头文本（移除排序指示器）
        for col in ['name', 'type', 'size', 'modified']:
            if col != column:
                current_col_text = self.tree.heading(col)['text']
                if current_col_text.endswith(' ▲') or current_col_text.endswith(' ▼'):
                    base_text = current_col_text.replace(' ▲', '').replace(' ▼', '')
                    self.tree.heading(col, text=base_text)
        
        # 分离文件夹和文件
        folders = []
        files = []
        
        for item in items:
            values = self.tree.item(item, 'values')
            if values[1] == '文件夹':
                folders.append((item, values))
            else:
                files.append((item, values))
        
        # 排序函数
        def get_sort_key(item_data):
            item, values = item_data
            col_index = ['name', 'type', 'size', 'modified'].index(column)
            value = values[col_index]
            
            if column == 'name':
                # 名称排序：去掉文件夹的[]符号
                name = values[0]
                if name.startswith('[') and name.endswith(']'):
                    name = name[1:-1]  # 去掉括号
                return name.lower()
            elif column == 'size':
                # 大小排序：转换为字节数
                size_str = value
                if not size_str:
                    return 0
                # 解析大小字符串
                if 'GB' in size_str:
                    return float(size_str.replace(' GB', '')) * 1024 * 1024 * 1024
                elif 'MB' in size_str:
                    return float(size_str.replace(' MB', '')) * 1024 * 1024
                elif 'KB' in size_str:
                    return float(size_str.replace(' KB', '')) * 1024
                elif 'B' in size_str:
                    return float(size_str.replace(' B', ''))
                else:
                    return 0
            elif column == 'modified':
                # 修改日期排序：转换为时间戳
                try:
                    import time
                    return time.mktime(time.strptime(value))
                except:
                    return 0
            else:
                # 类型或其他列：直接按字符串排序
                return value.lower()
        
        # 分别排序文件夹和文件
        folders.sort(key=get_sort_key, reverse=reverse)
        files.sort(key=get_sort_key, reverse=reverse)
        
        # 清空当前列表
        for item in items:
            self.tree.delete(item)
        
        # 重新插入项目（先文件夹后文件）
        for item, values in folders:
            self.tree.insert('', tk.END, values=values, tags=('folder',))
        
        for item, values in files:
            self.tree.insert('', tk.END, values=values, tags=('file',))
    
    def open_file(self, path):
        """打开文件"""
        try:
            # 根据操作系统使用默认程序打开文件
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', path])
            elif sys.platform == 'win32':  # Windows
                os.startfile(path)
            else:  # Linux
                subprocess.run(['xdg-open', path])
        except Exception as e:
            messagebox.showerror('打开文件失败', str(e))

class FinderBrowser(tk.Tk):
    """主应用窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.title('双窗口文件浏览器')
        self.geometry('1200x700')
        self.minsize(800, 600)
        
        # 在根窗口上存储对finder_app的引用，便于子组件访问
        self.finder_app = self
        
        # 默认将左侧窗口设为激活状态
        self.active_browser = None
        
        # 设置窗口图标（可选）
        
        # 创建菜单栏
        self.create_menu()
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建主内容区
        self.create_main_content()
        
        # 绑定全局按键事件
        self.bind_key_events()
        
        # 设置窗口位置（居中）
        self.center_window()
    
    def create_menu(self):
        """创建菜单栏"""
        self.menu_bar = tk.Menu(self)
        
        # 文件菜单
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label='新建文件夹', command=self.new_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='退出', command=self.quit)
        self.menu_bar.add_cascade(label='文件', menu=self.file_menu)
        
        # 编辑菜单
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.edit_menu.add_command(label='复制', command=self.copy)
        self.edit_menu.add_command(label='粘贴', command=self.paste)
        self.edit_menu.add_command(label='删除', command=self.delete)
        self.menu_bar.add_cascade(label='编辑', menu=self.edit_menu)
        
        # 视图菜单
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.view_menu.add_command(label='刷新', command=self.refresh_all)
        self.menu_bar.add_cascade(label='视图', menu=self.view_menu)
        
        # 前往菜单
        self.go_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.go_menu.add_command(label='主文件夹', command=lambda: self.navigate_to_home())
        self.go_menu.add_command(label='桌面', command=lambda: self.navigate_to_desktop())
        self.go_menu.add_command(label='文档', command=lambda: self.navigate_to_documents())
        self.go_menu.add_command(label='下载', command=lambda: self.navigate_to_downloads())
        self.go_menu.add_command(label='音乐', command=lambda: self.navigate_to_music())
        self.go_menu.add_command(label='图片', command=lambda: self.navigate_to_pictures())
        self.go_menu.add_command(label='影片', command=lambda: self.navigate_to_movies())
        self.menu_bar.add_cascade(label='前往', menu=self.go_menu)
        
        # 帮助菜单
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label='关于', command=self.show_about)
        self.menu_bar.add_cascade(label='帮助', menu=self.help_menu)
        
        # 设置菜单栏
        self.config(menu=self.menu_bar)
    
    def create_main_content(self):
        """创建主内容区"""
        # 创建分隔条
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # 添加侧边栏
        self.sidebar_frame = tk.Frame(self.paned, bg='#f2f2f7', width=200)
        # 存储finder_app引用到框架
        self.sidebar_frame.finder_app = self
        self.sidebar = Sidebar(self.sidebar_frame, on_path_select=self.on_sidebar_path_select)
        self.sidebar.pack(fill=tk.BOTH, expand=True)
        self.paned.add(self.sidebar_frame, weight=0)
        
        # 左侧浏览器
        self.left_frame = tk.Frame(self.paned, bg='#f2f2f7')
        # 存储finder_app引用到框架
        self.left_frame.finder_app = self
        self.left_browser = FileBrowser(self.left_frame, 
                                       on_path_change=self.on_left_path_change,
                                       on_file_select=self.on_file_select,
                                       on_folder_select=self.on_folder_select)
        # 直接给FileBrowser实例设置app引用
        self.left_browser.app = self
        self.left_browser.pack(fill=tk.BOTH, expand=True)
        self.paned.add(self.left_frame, weight=1)
        
        # 右侧浏览器
        self.right_frame = tk.Frame(self.paned, bg='#f2f2f7')
        # 存储finder_app引用到框架
        self.right_frame.finder_app = self
        self.right_browser = FileBrowser(self.right_frame,
                                        on_path_change=self.on_right_path_change,
                                        on_file_select=self.on_file_select,
                                        on_folder_select=self.on_folder_select)
        # 直接给FileBrowser实例设置app引用
        self.right_browser.app = self
        self.right_browser.pack(fill=tk.BOTH, expand=True)
        self.paned.add(self.right_frame, weight=1)
        
        # 设置初始分隔位置
        self.paned.sashpos(0, 200)
        self.paned.sashpos(1, 700)
        
        # 设置默认活动窗口
        self.set_active_browser(self.left_browser)
    
    def on_sidebar_path_select(self, path):
        """侧边栏路径选择回调"""
        # 在当前活动浏览器中打开选中的路径
        active_browser = self.get_active_browser()
        if active_browser:
            active_browser.navigate_to(path)
    
    def center_window(self):
        """居中窗口"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    def on_left_path_change(self, path):
        """左侧路径变化回调"""
        # 这里可以添加同步逻辑
        pass
    
    def on_right_path_change(self, path):
        """右侧路径变化回调"""
        # 这里可以添加同步逻辑
        pass
    
    def on_file_select(self, path):
        """文件选择回调"""
        self.selected_file = path
    
    def on_folder_select(self, path):
        """文件夹选择回调"""
        self.selected_folder = path
    
    def new_folder(self):
        """新建文件夹"""
        # 获取当前活动的浏览器
        active_browser = self.get_active_browser()
        if active_browser:
            folder_name = simpledialog.askstring('新建文件夹', '请输入文件夹名称:')
            if folder_name:
                try:
                    new_path = os.path.join(active_browser.current_path, folder_name)
                    os.makedirs(new_path)
                    active_browser.refresh_file_list()
                except Exception as e:
                    messagebox.showerror('创建失败', str(e))
    
    class FileConflictDialog(tk.Toplevel):
        """文件冲突处理对话框，支持全局策略"""
        def __init__(self, parent, source_name, target_name):
            super().__init__(parent)
            self.title("文件冲突")
            self.transient(parent)
            self.resizable(False, False)
            self.geometry("450x250")
            
            # 设置默认结果
            self.result = "cancel"  # "skip", "replace", "cancel"
            self.apply_to_all = False  # 是否应用到所有文件
            
            # 创建内容框架
            content_frame = ttk.Frame(self, padding=15)
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            # 显示冲突信息
            message = f"目标位置已存在同名文件:\n\n{target_name}\n\n您想如何处理此冲突？"
            self.message_label = ttk.Label(content_frame, text=message, wraplength=400)
            self.message_label.pack(pady=(0, 15))
            
            # 第一行按钮
            first_row = ttk.Frame(content_frame)
            first_row.pack(fill=tk.X, pady=(0, 10))
            
            # 跳过按钮
            self.skip_btn = ttk.Button(first_row, text="跳过", command=self.skip)
            self.skip_btn.pack(side=tk.LEFT, padx=5)
            
            # 全部跳过按钮
            self.skip_all_btn = ttk.Button(first_row, text="全部跳过", command=self.skip_all)
            self.skip_all_btn.pack(side=tk.LEFT, padx=5)
            
            # 覆盖按钮
            self.replace_btn = ttk.Button(first_row, text="覆盖", command=self.replace)
            self.replace_btn.pack(side=tk.LEFT, padx=5)
            
            # 全部覆盖按钮
            self.replace_all_btn = ttk.Button(first_row, text="全部覆盖", command=self.replace_all)
            self.replace_all_btn.pack(side=tk.LEFT, padx=5)
            
            # 取消按钮
            self.cancel_btn = ttk.Button(first_row, text="取消", command=self.cancel)
            self.cancel_btn.pack(side=tk.RIGHT, padx=5)
            
            # 模态对话框
            self.grab_set()
            self.wait_window(self)
            
        def skip(self):
            self.result = "skip"
            self.apply_to_all = False
            self.destroy()
            
        def skip_all(self):
            self.result = "skip"
            self.apply_to_all = True
            self.destroy()
            
        def replace(self):
            self.result = "replace"
            self.apply_to_all = False
            self.destroy()
            
        def replace_all(self):
            self.result = "replace"
            self.apply_to_all = True
            self.destroy()
            
        def cancel(self):
            self.result = "cancel"
            self.apply_to_all = False
            self.destroy()
    
    class CopyProgressDialog(tk.Toplevel):
        """复制进度对话框"""
        def __init__(self, parent, title="复制文件"):
            super().__init__(parent)
            self.title(title)
            self.transient(parent)
            self.resizable(False, False)
            self.geometry("400x120")
            
            # 禁止关闭按钮
            self.protocol("WM_DELETE_WINDOW", lambda: None)
            
            # 创建进度条框架
            self.progress_frame = ttk.Frame(self, padding=10)
            self.progress_frame.pack(fill=tk.BOTH, expand=True)
            
            # 进度条标签
            self.progress_label = ttk.Label(self.progress_frame, text="正在准备复制...")
            self.progress_label.pack(fill=tk.X, pady=(0, 10))
            
            # 进度条
            self.progress_var = tk.DoubleVar()
            self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, length=380)
            self.progress_bar.pack(fill=tk.X)
            
            # 取消按钮
            self.cancel_btn = ttk.Button(self.progress_frame, text="取消", command=self.cancel)
            self.cancel_btn.pack(pady=10)
            
            # 取消标志
            self.cancelled = False
            
        def update_progress(self, progress, current_file=""):
            """更新进度条"""
            self.progress_var.set(progress)
            if current_file:
                self.progress_label.config(text=f"正在复制: {os.path.basename(current_file)}")
            self.update_idletasks()
            
        def cancel(self):
            """取消复制操作"""
            self.cancelled = True
            self.progress_label.config(text="正在取消复制...")
            self.cancel_btn.config(state=tk.DISABLED)
    
    def bind_key_events(self):
        """绑定全局按键事件，确保操作仅作用于激活窗口"""
        # 文件操作快捷键
        self.bind('<Control-c>', lambda e: self.copy())
        self.bind('<Control-x>', lambda e: self.move())
        self.bind('<Control-v>', lambda e: self.paste())
        self.bind('<Delete>', lambda e: self.delete())
        self.bind('<F5>', lambda e: self.refresh_all())
        
        # 窗口切换快捷键
        self.bind('<Control-1>', lambda e: self.set_active_browser(self.left_browser))
        self.bind('<Control-2>', lambda e: self.set_active_browser(self.right_browser))
        
        # 添加Tab键切换窗口
        self.bind('<Tab>', lambda e: self.toggle_active_browser())
    
    def _copy_with_dialog(self, source_path, target_path, display_name, target_browser):
        """带进度条的复制操作"""
        # 计算总文件大小
        total_size = self._get_directory_size(source_path)
        
        # 创建进度条对话框
        progress_dialog = self.CopyProgressDialog(self, f"复制 {display_name}")
        
        # 使用线程执行复制操作
        copied_size = [0]
        def copy_task():
            try:
                if os.path.isdir(source_path):
                    shutil.copytree(source_path, target_path, copy_function=lambda s, d: self._copy_file_with_progress(s, d, total_size, copied_size, progress_dialog))
                else:
                    self._copy_file_with_progress(source_path, target_path, total_size, copied_size, progress_dialog)
                
                # 检查是否被取消
                if not progress_dialog.cancelled:
                    # 刷新目标浏览器
                    target_browser.refresh_file_list()
                    # 更新状态栏
                    self.status_var.set(f"已复制: {display_name}")
            except OSError as e:
                if not progress_dialog.cancelled:
                    self.status_var.set(f"复制失败: {str(e)}")
                    messagebox.showerror("错误", f"复制失败:\n{str(e)}")
            finally:
                # 关闭进度条对话框
                progress_dialog.destroy()
        
        # 启动复制线程
        copy_thread = threading.Thread(target=copy_task)
        copy_thread.daemon = True
        copy_thread.start()
    
    def _copy_with_progress(self, source_dir, target_dir, total_size, copied_size, progress_dialog):
        """递归复制目录并显示进度"""
        # 确保目标目录存在
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        # 检查是否被取消
        if progress_dialog.cancelled:
            raise OSError("复制操作已取消")
        
        # 遍历源目录中的所有项目
        for item in os.listdir(source_dir):
            source_item = os.path.join(source_dir, item)
            target_item = os.path.join(target_dir, item)
            
            if os.path.isdir(source_item):
                # 如果是子目录，递归复制
                self._copy_with_progress(source_item, target_item, total_size, copied_size, progress_dialog)
            else:
                # 如果是文件，复制并更新进度
                self._copy_file_with_progress(source_item, target_item, total_size, copied_size, progress_dialog)
    
    def _copy_file_with_progress(self, source, dest, total_size, copied_size, progress_dialog):
        """复制单个文件并更新进度"""
        # 检查是否被取消
        if progress_dialog.cancelled:
            raise OSError("复制操作已取消")
        
        # 复制文件
        shutil.copy2(source, dest)
        
        # 更新已复制大小
        file_size = os.path.getsize(source)
        copied_size[0] += file_size
        
        # 计算进度百分比
        progress = (copied_size[0] / total_size) * 100 if total_size > 0 else 100
        
        # 更新进度条
        progress_dialog.update_progress(progress, source)
        
        return dest
    
    def _get_directory_size(self, path):
        """计算目录总大小"""
        total_size = 0
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception:
            pass
        
        # 如果获取失败，返回一个默认值
        return total_size if total_size > 0 else 1
    
    def paste(self):
        """粘贴"""
        # 实现粘贴功能
        pass
    
    def delete(self):
        """删除选中的多个文件或文件夹，支持删除非空目录"""
        active_browser = self.get_active_browser()
        if not active_browser:
            return
        
        selected_items = active_browser.tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请选择要删除的文件或文件夹")
            return
        
        # 检查是否为SFTP浏览器
        if hasattr(active_browser, 'is_sftp') and active_browser.is_sftp:
            # 如果是SFTP浏览器，调用SFTP多选删除方法
            print("[DEBUG] 检测到SFTP浏览器，调用SFTP多选删除方法")
            import sys
            sys.stdout.flush()
            
            # 调用SFTP多选删除方法
            self._sftp_delete_multiple(active_browser, active_browser.sftp_fs, selected_items)
            return
        
        # 本地文件系统删除逻辑
        # 准备文件列表
        items_to_delete = []
        has_non_empty_dir = False
        
        for item in selected_items:
            # 获取选中项的显示名称
            display_name = active_browser.tree.item(item, "values")[0]
            
            # 处理带括号的文件夹名称
            if display_name.startswith('[') and display_name.endswith(']'):
                actual_name = display_name[1:-1]  # 去掉括号
            else:
                actual_name = display_name
            
            # 构建完整路径
            path = os.path.join(active_browser.current_path, actual_name)
            items_to_delete.append((path, display_name, os.path.isdir(path)))
            
            # 检查是否有非空目录
            if os.path.isdir(path) and len(os.listdir(path)) > 0:
                has_non_empty_dir = True
        
        # 根据选择数量和内容显示确认消息
        if len(items_to_delete) == 1:
            path, display_name, is_dir = items_to_delete[0]
            if is_dir and len(os.listdir(path)) > 0:
                confirm_msg = f"确定要删除目录 '{display_name}' 及其所有内容吗？此操作不可撤销！"
            else:
                confirm_msg = f"确定要删除 '{display_name}' 吗？"
        else:
            if has_non_empty_dir:
                confirm_msg = f"确定要删除选中的 {len(items_to_delete)} 个项目（包含非空目录）及其所有内容吗？此操作不可撤销！"
            else:
                confirm_msg = f"确定要删除选中的 {len(items_to_delete)} 个项目吗？"
        
        # 确认删除
        response = messagebox.askyesno("确认删除", confirm_msg)
        if response:
            success_count = 0
            error_files = []
            
            for path, display_name, is_dir in items_to_delete:
                try:
                    if is_dir:
                        # 使用shutil.rmtree删除目录及其所有内容
                        shutil.rmtree(path)
                    else:
                        os.remove(path)  # 删除文件
                    success_count += 1
                except OSError as e:
                    error_files.append(f"{display_name}: {str(e)}")
            
            # 刷新文件列表
            active_browser.refresh_file_list()
            
            # 显示结果
            if error_files:
                error_msg = "部分文件删除失败:\n" + "\n".join(error_files)
                messagebox.showerror("删除结果", error_msg)
                self.status_var.set(f"已删除 {success_count} 个项目，{len(error_files)} 个失败")
            else:
                self.status_var.set(f"已删除 {success_count} 个项目")
    
    def refresh_all(self):
        """刷新所有窗口"""
        # 刷新侧边栏
        self.sidebar.refresh_content()
        # 刷新左右浏览器
        self.left_browser.refresh_file_list()
        self.right_browser.refresh_file_list()
    
    def navigate_to_home(self):
        """导航到主文件夹"""
        active_browser = self.get_active_browser()
        if active_browser:
            home = os.path.expanduser('~')
            active_browser.navigate_to(home)
    
    def navigate_to_desktop(self):
        """导航到桌面"""
        active_browser = self.get_active_browser()
        if active_browser:
            desktop = os.path.expanduser('~/Desktop')
            if os.path.exists(desktop):
                active_browser.navigate_to(desktop)
    
    def navigate_to_documents(self):
        """导航到文档"""
        active_browser = self.get_active_browser()
        if active_browser:
            docs = os.path.expanduser('~/Documents')
            if os.path.exists(docs):
                active_browser.navigate_to(docs)
    
    def navigate_to_downloads(self):
        """导航到下载"""
        active_browser = self.get_active_browser()
        if active_browser:
            downloads = os.path.expanduser('~/Downloads')
            if os.path.exists(downloads):
                active_browser.navigate_to(downloads)
    
    def navigate_to_music(self):
        """导航到音乐"""
        active_browser = self.get_active_browser()
        if active_browser:
            music = os.path.expanduser('~/Music')
            if os.path.exists(music):
                active_browser.navigate_to(music)
    
    def navigate_to_pictures(self):
        """导航到图片"""
        active_browser = self.get_active_browser()
        if active_browser:
            pictures = os.path.expanduser('~/Pictures')
            if os.path.exists(pictures):
                active_browser.navigate_to(pictures)
    
    def navigate_to_movies(self):
        """导航到影片"""
        active_browser = self.get_active_browser()
        if active_browser:
            movies = os.path.expanduser('~/Movies')
            if os.path.exists(movies):
                active_browser.navigate_to(movies)
    
    def get_active_browser(self):
        """获取当前活动的浏览器"""
        # 如果没有设置活动浏览器，默认将左侧设为活动
        if self.active_browser is None:
            self.set_active_browser(self.left_browser)
        return self.active_browser
        
    def set_active_browser(self, browser):
        """设置激活的浏览器窗口，确保总有一个窗口处于激活状态"""
        # 停用另一个窗口
        if browser == self.left_browser:
            self.left_browser.set_active(True)
            self.right_browser.set_active(False)
            # 同时更新外层框架的背景色
            self.left_frame.configure(bg='#e3f2fd')
            self.right_frame.configure(bg='#f2f2f7')
        else:
            self.left_browser.set_active(False)
            self.right_browser.set_active(True)
            # 同时更新外层框架的背景色
            self.left_frame.configure(bg='#f2f2f7')
            self.right_frame.configure(bg='#e3f2fd')
        
        # 更新活动浏览器引用
        self.active_browser = browser
        browser.tree.focus_force()  # 确保焦点在文件列表上
        
        # 更新状态栏显示当前激活的窗口
        self.status_var = getattr(self, 'status_var', tk.StringVar())
        self.status_var.set(f"活动窗口: {os.path.basename(browser.current_path)}")
        
    def toggle_active_browser(self):
        """切换激活的浏览器窗口"""
        if self.active_browser == self.left_browser:
            self.set_active_browser(self.right_browser)
        else:
            self.set_active_browser(self.left_browser)
        return 'break'  # 阻止默认Tab行为
    
    def create_toolbar(self):
        """创建工具栏，包含复制、移动、删除三个按钮以及显示/隐藏隐藏文件的切换按钮和新建目录按钮"""
        self.toolbar = tk.Frame(self, bg='#f2f2f7', bd=1, relief=tk.FLAT)
        
        # 复制按钮
        self.copy_btn = ttk.Button(self.toolbar, text='复制', command=self.copy)
        self.copy_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 移动按钮
        self.move_btn = ttk.Button(self.toolbar, text='移动', command=self.move)
        self.move_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 删除按钮
        self.delete_btn = ttk.Button(self.toolbar, text='删除', command=self.delete)
        self.delete_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 新建目录按钮
        self.new_folder_btn = ttk.Button(self.toolbar, text='新建目录', command=self.new_folder)
        self.new_folder_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 分隔符
        self.toolbar_separator = ttk.Separator(self.toolbar, orient=tk.VERTICAL)
        self.toolbar_separator.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)
        
        # 显示/隐藏隐藏文件切换按钮
        self.show_hidden_var = tk.BooleanVar(value=False)
        self.toggle_hidden_btn = ttk.Checkbutton(self.toolbar, text='显示隐藏文件', 
                                               variable=self.show_hidden_var,
                                               command=self.toggle_hidden_files)
        self.toggle_hidden_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # SFTP连接按钮
        self.sftp_btn = ttk.Button(self.toolbar, text='SFTP连接', command=self.open_sftp_dialog)
        self.sftp_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 弹出所有USB设备按钮
        self.eject_btn = ttk.Button(self.toolbar, text='弹出USB设备', command=self.eject_all_devices)
        self.eject_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 打包工具栏
        self.toolbar.pack(fill=tk.X, padx=5, pady=5)
        
    def toggle_hidden_files(self):
        """切换是否显示隐藏文件"""
        # 更新两个浏览器的显示隐藏文件标志
        self.left_browser.show_hidden = self.show_hidden_var.get()
        self.right_browser.show_hidden = self.show_hidden_var.get()
        
        # 刷新两个浏览器的文件列表
        self.left_browser.refresh_file_list()
        self.right_browser.refresh_file_list()
    
    def new_folder(self):
        """在当前活动窗口中新建目录"""
        # 获取活动浏览器窗口
        active_browser = self.get_active_browser()
        
        # 弹出对话框输入目录名
        new_folder_name = tk.simpledialog.askstring("新建目录", "请输入新目录名称:", parent=self)
        
        if new_folder_name and active_browser:
            # 检查目录名是否合法
            if self.is_valid_filename(new_folder_name):
                # 检查是否为SFTP浏览器
                if hasattr(active_browser, 'is_sftp') and active_browser.is_sftp:
                    # SFTP创建目录
                    print(f"[DEBUG] 检测到SFTP浏览器，创建SFTP目录: {new_folder_name}")
                    import sys
                    sys.stdout.flush()
                    
                    # 构建完整路径
                    if active_browser.current_path == '/':
                        new_folder_path = f"/{new_folder_name}"
                    else:
                        new_folder_path = f"{active_browser.current_path}/{new_folder_name}"
                    
                    print(f"[DEBUG] SFTP创建目录路径: {new_folder_path}")
                    sys.stdout.flush()
                    
                    try:
                        # 创建新目录
                        active_browser.sftp_fs.mkdir(new_folder_path)
                        # 刷新文件列表
                        active_browser.refresh_file_list()
                        # 显示成功消息
                        self.status_var.set(f"成功创建目录: {new_folder_name}")
                        print(f"[DEBUG] SFTP目录创建成功: {new_folder_path}")
                        sys.stdout.flush()
                    except Exception as e:
                        # 显示错误消息
                        error_msg = f"创建目录失败: {str(e)}"
                        self.status_var.set(error_msg)
                        print(f"[ERROR] {error_msg}")
                        sys.stdout.flush()
                        tk.messagebox.showerror("错误", f"无法创建目录:\n{str(e)}")
                else:
                    # 本地文件系统创建目录
                    # 构建完整路径
                    new_folder_path = os.path.join(active_browser.current_path, new_folder_name)
                    
                    try:
                        # 创建新目录
                        os.makedirs(new_folder_path)
                        # 刷新文件列表
                        active_browser.refresh_file_list()
                        # 显示成功消息
                        self.status_var.set(f"成功创建目录: {new_folder_name}")
                    except OSError as e:
                        # 显示错误消息
                        self.status_var.set(f"创建目录失败: {str(e)}")
                        tk.messagebox.showerror("错误", f"无法创建目录:\n{str(e)}")
            else:
                # 显示无效文件名的错误
                self.status_var.set("无效的目录名称")
                tk.messagebox.showerror("错误", "目录名称包含无效字符或为空")
    
    def is_valid_filename(self, filename):
        """检查文件名是否合法"""
        import re
        # 不允许包含这些字符: / \ : * ? " < > |
        if not filename:
            return False
        if re.search(r'[<>"/\\|*?:]', filename):
            return False
        return True
        
    def is_system_volume(self, volume_name, mount_point):
        """判断是否为系统卷或主硬盘"""
        # 系统卷标记
        system_volumes = [
            '/',  # 根目录
            '/System',
            '/Library',
            '/Users',
            '/Applications',
            '/Volumes/Macintosh HD',  # 默认系统卷名
            '/Volumes/Macintosh HD - Data',  # 默认数据卷名
            '/Volumes/Recovery'  # 恢复分区
        ]
        
        # 检查是否为系统卷
        if mount_point in system_volumes:
            return True
        
        # 检查卷名是否包含系统相关关键词
        system_keywords = ['macintosh', 'hd', 'system', 'boot', 'recovery', 'vm', 'home']
        if any(keyword in volume_name.lower() for keyword in system_keywords):
            # 但允许用户有重名的外部卷，通过检查挂载点进一步确认
            if mount_point.startswith('/Volumes/') and mount_point not in system_volumes:
                return False
            return True
        
        return False
        
    def get_all_mounted_volumes(self):
        """获取所有挂载的卷信息（包括系统卷）"""
        try:
            # 获取挂载点信息
            mount_result = subprocess.run(
                ["mount"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 解析挂载点信息
            volumes = {}
            mount_lines = mount_result.stdout.strip().split('\n')
            
            for line in mount_lines:
                # 匹配所有挂载点
                if ' on ' in line:
                    parts = line.split(' on ')
                    if len(parts) >= 2:
                        mount_info = parts[1]
                        # 提取挂载点，去掉后面的文件系统信息
                        if ' (' in mount_info:
                            mount_point = mount_info.split(' (')[0]
                        else:
                            mount_point = mount_info
                        
                        # 获取卷名
                        if mount_point == '/':
                            volume_name = "根目录"
                        elif '/' in mount_point:
                            volume_name = mount_point.split('/')[-1] or mount_point
                        else:
                            volume_name = mount_point
                        
                        volumes[volume_name] = mount_point
            
            return volumes
            
        except Exception as e:
            print(f"获取挂载信息失败: {e}")
            return {}
            
    def eject_volume(self, volume_name, mount_point):
        """弹出指定的卷"""
        try:
            # 使用diskutil eject命令安全弹出
            result = subprocess.run(
                ["diskutil", "eject", mount_point],
                check=True,
                capture_output=True,
                text=True
            )
            return True
            
        except subprocess.CalledProcessError as e:
            # 如果直接弹出失败，尝试先卸载
            try:
                result = subprocess.run(
                    ["diskutil", "unmount", mount_point],
                    check=True,
                    capture_output=True,
                    text=True
                )
                return True
                
            except subprocess.CalledProcessError as e2:
                return False
                
        except Exception as e:
            return False
            
    def eject_all_devices(self):
        """弹出所有外置USB设备，无需确认但显示弹出的卷名"""
        # 获取所有挂载的卷
        all_volumes = self.get_all_mounted_volumes()
        
        if not all_volumes:
            messagebox.showinfo("提示", "没有找到任何挂载的卷")
            return
        
        # 识别外部卷
        external_volumes = {}
        for volume_name, mount_point in all_volumes.items():
            if not self.is_system_volume(volume_name, mount_point) and mount_point.startswith('/Volumes/'):
                external_volumes[volume_name] = mount_point
        
        if not external_volumes:
            messagebox.showinfo("提示", "没有找到可弹出的外部卷")
            return
        
        # 创建弹出进度窗口
        progress_window = tk.Toplevel(self)
        progress_window.title("弹出设备中...")
        progress_window.geometry("300x150")
        progress_window.resizable(False, False)
        progress_window.transient(self)  # 设置为主窗口的子窗口
        progress_window.grab_set()  # 模态窗口
        
        # 居中显示
        progress_window.update_idletasks()
        width = progress_window.winfo_width()
        height = progress_window.winfo_height()
        x = (self.winfo_width() // 2) - (width // 2) + self.winfo_x()
        y = (self.winfo_height() // 2) - (height // 2) + self.winfo_y()
        progress_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # 显示正在弹出的设备信息
        status_label = tk.Label(progress_window, text="准备弹出设备...", font=("Arial", 10))
        status_label.pack(pady=20)
        
        # 弹出外部卷
        success_count = 0
        fail_count = 0
        failed_devices = []
        success_devices = []
        
        # 更新进度窗口
        def update_progress(text):
            status_label.config(text=text)
            progress_window.update()
        
        import time
        for volume_name, mount_point in external_volumes.items():
            # 显示正在弹出的设备卷名
            update_progress(f"正在弹出: {volume_name}...")
            
            if self.eject_volume(volume_name, mount_point):
                success_count += 1
                success_devices.append(volume_name)
            else:
                fail_count += 1
                failed_devices.append(volume_name)
            
            # 短暂延迟，避免操作过快
            time.sleep(0.5)
        
        # 关闭进度窗口
        progress_window.destroy()
        
        # 显示结果
        if success_devices:
            success_list = "\n".join([f"- {name}" for name in success_devices])
            result_message = f"成功弹出以下设备:\n{success_list}\n"
        else:
            result_message = "没有成功弹出任何设备\n"
            
        if fail_count > 0:
            result_message += f"\n弹出失败: {fail_count} 个设备\n"
            result_message += f"失败的设备: {', '.join(failed_devices)}"
        
        messagebox.showinfo("操作完成", result_message)
        
        # 刷新文件列表和侧边栏，以反映设备弹出后的状态
        self.sidebar.refresh_content()
        self.left_browser.refresh_file_list()
        self.right_browser.refresh_file_list()
    
    def copy(self):
        """复制多个文件或文件夹，显示进度条，支持全局冲突处理策略和SFTP"""
        active_browser = self.get_active_browser()
        if not active_browser:
            return
        
        selected_items = active_browser.tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请选择要复制的文件或文件夹")
            return
        
        # 选择目标浏览器窗口（另一个窗口）
        if active_browser == self.left_browser:
            target_browser = self.right_browser
        else:
            target_browser = self.left_browser
        
        # 准备文件列表
        files_to_copy = []
        for item in selected_items:
            # 获取选中项的显示名称
            display_name = active_browser.tree.item(item, "values")[0]
            
            # 处理带括号的文件夹名称
            if display_name.startswith('[') and display_name.endswith(']'):
                actual_name = display_name[1:-1]  # 去掉括号
            else:
                actual_name = display_name
            
            # 构建完整路径，根据是否为SFTP模式
            if hasattr(active_browser, 'is_sftp') and active_browser.is_sftp:
                source_path = active_browser.sftp_fs.join(active_browser.current_path, actual_name)
            else:
                source_path = os.path.join(active_browser.current_path, actual_name)
            
            if hasattr(target_browser, 'is_sftp') and target_browser.is_sftp:
                target_path = target_browser.sftp_fs.join(target_browser.current_path, actual_name)
            else:
                target_path = os.path.join(target_browser.current_path, actual_name)
            
            # 存储源浏览器、目标浏览器和路径信息
            files_to_copy.append((active_browser, target_browser, source_path, target_path, display_name))
        
        # 计算总文件大小
        total_size = 0
        for source_browser, _, source_path, _, _ in files_to_copy:
            if hasattr(source_browser, 'is_sftp') and source_browser.is_sftp:
                # SFTP文件大小计算
                try:
                    stat = source_browser.sftp_fs.stat(source_path)
                    total_size += stat.st_size
                except Exception:
                    # 如果无法获取大小，跳过
                    pass
            else:
                # 本地文件大小计算
                total_size += self._get_directory_size(source_path)
        
        # 创建进度条对话框
        progress_dialog = self.CopyProgressDialog(self, f"复制 {len(files_to_copy)} 个项目")
        
        # 使用线程执行复制操作
        copied_size = [0]
        def copy_task():
            try:
                success_count = 0
                skipped_count = 0
                global_strategy = None  # 全局策略：None, "skip", "replace"
                
                for source_browser, target_browser, source_path, target_path, display_name in files_to_copy:
                    # 检查是否被取消
                    if progress_dialog.cancelled:
                        raise OSError("复制操作已取消")
                    
                    # 更新进度条显示当前复制的文件
                    progress_dialog.update_progress(copied_size[0] / total_size * 100 if total_size > 0 else 0, source_path)
                    
                    # 检查文件冲突
                    target_exists = False
                    if hasattr(target_browser, 'is_sftp') and target_browser.is_sftp:
                        target_exists = target_browser.sftp_fs.exists(target_path)
                    else:
                        target_exists = os.path.exists(target_path)
                    
                    if target_exists:
                        # 如果已有全局策略，则直接应用
                        if global_strategy == "skip":
                            skipped_count += 1
                            continue
                        elif global_strategy == "replace":
                            # 移除目标文件/目录
                            if hasattr(target_browser, 'is_sftp') and target_browser.is_sftp:
                                if target_browser.sftp_fs.isdir(target_path):
                                    # SFTP递归删除目录的辅助函数
                                    def sftp_recursive_delete(sftp, path):
                                        for item in sftp.listdir_attr(path):
                                            item_path = f"{path}/{item.filename}"
                                            if stat.S_ISDIR(item.st_mode):
                                                sftp_recursive_delete(sftp, item_path)
                                            else:
                                                sftp.remove(item_path)
                                        sftp.rmdir(path)
                                    sftp_recursive_delete(target_browser.sftp_fs.sftp, target_path)
                                else:
                                    target_browser.sftp_fs.remove(target_path)
                            else:
                                if os.path.isdir(target_path):
                                    shutil.rmtree(target_path)
                                else:
                                    os.remove(target_path)
                        else:
                            # 显示冲突处理对话框
                            conflict_dialog = self.FileConflictDialog(self, display_name, display_name)
                            
                            if conflict_dialog.result == "cancel":
                                # 用户取消整个操作
                                progress_dialog.cancelled = True
                                raise OSError("复制操作已取消")
                            elif conflict_dialog.result == "skip":
                                # 跳过当前文件
                                skipped_count += 1
                                # 如果用户选择应用到所有，设置全局策略
                                if conflict_dialog.apply_to_all:
                                    global_strategy = "skip"
                                continue
                            else:  # replace
                                # 移除目标文件/目录
                                if hasattr(target_browser, 'is_sftp') and target_browser.is_sftp:
                                    if target_browser.sftp_fs.isdir(target_path):
                                        # SFTP递归删除目录
                                        def sftp_recursive_delete(sftp, path):
                                            for item in sftp.listdir_attr(path):
                                                item_path = f"{path}/{item.filename}"
                                                if stat.S_ISDIR(item.st_mode):
                                                    sftp_recursive_delete(sftp, item_path)
                                                else:
                                                    sftp.remove(item_path)
                                            sftp.rmdir(path)
                                        sftp_recursive_delete(target_browser.sftp_fs.sftp, target_path)
                                    else:
                                        target_browser.sftp_fs.remove(target_path)
                                else:
                                    if os.path.isdir(target_path):
                                        shutil.rmtree(target_path)
                                    else:
                                        os.remove(target_path)
                                # 如果用户选择应用到所有，设置全局策略
                                if conflict_dialog.apply_to_all:
                                    global_strategy = "replace"
                    
                    # 处理四种复制情况
                    is_source_sftp = hasattr(source_browser, 'is_sftp') and source_browser.is_sftp
                    is_target_sftp = hasattr(target_browser, 'is_sftp') and target_browser.is_sftp
                    
                    # 复制文件/目录
                    if is_source_sftp and is_target_sftp:
                        # SFTP到SFTP复制
                        if source_browser.sftp_fs.isdir(source_path):
                            # 递归创建目录
                            def sftp_recursive_copy(source_sftp, target_sftp, source_path, target_path):
                                # 创建目标目录
                                if not target_sftp.exists(target_path):
                                    target_sftp.mkdir(target_path)
                                
                                # 复制目录内容
                                for item in source_sftp.listdir_attr(source_path):
                                    item_source_path = f"{source_path}/{item.filename}"
                                    item_target_path = f"{target_path}/{item.filename}"
                                    
                                    if stat.S_ISDIR(item.st_mode):
                                        # 递归复制子目录
                                        sftp_recursive_copy(source_sftp, target_sftp, item_source_path, item_target_path)
                                    else:
                                        # 复制单个文件
                                        with source_sftp.open(item_source_path, 'rb') as source_file:
                                            with target_sftp.open(item_target_path, 'wb') as target_file:
                                                chunk_size = 8192
                                                while True:
                                                    data = source_file.read(chunk_size)
                                                    if not data:
                                                        break
                                                    target_file.write(data)
                                                # 更新已复制大小
                                                copied_size[0] += item.st_size
                                                progress_dialog.update_progress(copied_size[0] / total_size * 100 if total_size > 0 else 0, item_source_path)
                                
                                # 检查是否被取消
                                if progress_dialog.cancelled:
                                    raise OSError("复制操作已取消")
                            
                            # 确保目标目录的父目录存在
                            target_dir_parent = target_path.rsplit('/', 1)[0]
                            if target_dir_parent and not target_browser.sftp_fs.exists(target_dir_parent):
                                # 创建父目录
                                parts = target_dir_parent.split('/')
                                path_so_far = '/' if parts[0] else ''
                                for part in parts:
                                    if part:
                                        path_so_far = f"{path_so_far}/{part}" if path_so_far else part
                                        if not target_browser.sftp_fs.exists(path_so_far):
                                            target_browser.sftp_fs.mkdir(path_so_far)
                            
                            # 开始递归复制
                            sftp_recursive_copy(source_browser.sftp_fs.sftp, target_browser.sftp_fs.sftp, source_path, target_path)
                        else:
                            # 复制单个SFTP文件
                            with source_browser.sftp_fs.sftp.open(source_path, 'rb') as source_file:
                                with target_browser.sftp_fs.sftp.open(target_path, 'wb') as target_file:
                                    chunk_size = 8192
                                    while True:
                                        data = source_file.read(chunk_size)
                                        if not data:
                                            break
                                        target_file.write(data)
                                    # 更新已复制大小
                                    file_stat = source_browser.sftp_fs.stat(source_path)
                                    copied_size[0] += file_stat.st_size
                    
                    elif is_source_sftp and not is_target_sftp:
                        # SFTP到本地（下载）
                        if source_browser.sftp_fs.isdir(source_path):
                            # 递归下载目录
                            def sftp_download_recursive(sftp, source_path, target_path):
                                # 创建目标目录
                                if not os.path.exists(target_path):
                                    os.makedirs(target_path)
                                
                                # 下载目录内容
                                for item in sftp.listdir_attr(source_path):
                                    item_source_path = f"{source_path}/{item.filename}"
                                    item_target_path = os.path.join(target_path, item.filename)
                                    
                                    if stat.S_ISDIR(item.st_mode):
                                        # 递归下载子目录
                                        sftp_download_recursive(sftp, item_source_path, item_target_path)
                                    else:
                                        # 下载单个文件
                                        sftp.get(item_source_path, item_target_path)
                                        # 更新已复制大小
                                        copied_size[0] += item.st_size
                                        progress_dialog.update_progress(copied_size[0] / total_size * 100 if total_size > 0 else 0, item_source_path)
                                
                                # 检查是否被取消
                                if progress_dialog.cancelled:
                                    raise OSError("复制操作已取消")
                            
                            # 确保目标目录的父目录存在
                            target_dir_parent = os.path.dirname(target_path)
                            if target_dir_parent and not os.path.exists(target_dir_parent):
                                os.makedirs(target_dir_parent)
                            
                            # 开始递归下载
                            sftp_download_recursive(source_browser.sftp_fs.sftp, source_path, target_path)
                        else:
                            # 下载单个SFTP文件
                            # 确保目标目录存在
                            target_dir = os.path.dirname(target_path)
                            if target_dir and not os.path.exists(target_dir):
                                os.makedirs(target_dir)
                            
                            # 下载文件
                            source_browser.sftp_fs.get(source_path, target_path)
                            # 更新已复制大小
                            file_stat = source_browser.sftp_fs.stat(source_path)
                            copied_size[0] += file_stat.st_size
                    
                    elif not is_source_sftp and is_target_sftp:
                        # 本地到SFTP（上传）
                        if os.path.isdir(source_path):
                            # 递归上传目录
                            def sftp_upload_recursive(sftp, source_path, target_path):
                                # 创建目标目录
                                if not sftp.exists(target_path):
                                    sftp.mkdir(target_path)
                                
                                # 上传目录内容
                                for item in os.listdir(source_path):
                                    item_source_path = os.path.join(source_path, item)
                                    item_target_path = f"{target_path}/{item}"
                                    
                                    if os.path.isdir(item_source_path):
                                        # 递归上传子目录
                                        sftp_upload_recursive(sftp, item_source_path, item_target_path)
                                    else:
                                        # 上传单个文件
                                        sftp.put(item_source_path, item_target_path)
                                        # 更新已复制大小
                                        copied_size[0] += os.path.getsize(item_source_path)
                                        progress_dialog.update_progress(copied_size[0] / total_size * 100 if total_size > 0 else 0, item_source_path)
                                
                                # 检查是否被取消
                                if progress_dialog.cancelled:
                                    raise OSError("复制操作已取消")
                            
                            # 确保目标目录的父目录存在
                            target_dir_parent = target_path.rsplit('/', 1)[0]
                            if target_dir_parent and not target_browser.sftp_fs.exists(target_dir_parent):
                                # 创建父目录
                                parts = target_dir_parent.split('/')
                                path_so_far = '/' if parts[0] else ''
                                for part in parts:
                                    if part:
                                        path_so_far = f"{path_so_far}/{part}" if path_so_far else part
                                        if not target_browser.sftp_fs.exists(path_so_far):
                                            target_browser.sftp_fs.mkdir(path_so_far)
                            
                            # 开始递归上传
                            sftp_upload_recursive(target_browser.sftp_fs.sftp, source_path, target_path)
                        else:
                            # 上传单个本地文件
                            # 确保目标目录存在
                            target_dir = target_path.rsplit('/', 1)[0]
                            if target_dir and not target_browser.sftp_fs.exists(target_dir):
                                # 创建目录结构
                                parts = target_dir.split('/')
                                path_so_far = '/' if parts[0] else ''
                                for part in parts:
                                    if part:
                                        path_so_far = f"{path_so_far}/{part}" if path_so_far else part
                                        if not target_browser.sftp_fs.exists(path_so_far):
                                            target_browser.sftp_fs.mkdir(path_so_far)
                            
                            # 上传文件
                            target_browser.sftp_fs.put(source_path, target_path)
                            # 更新已复制大小
                            copied_size[0] += os.path.getsize(source_path)
                    
                    else:
                        # 本地到本地复制（原始实现）
                        if os.path.isdir(source_path):
                            # 复制目录
                            shutil.copytree(source_path, target_path, copy_function=lambda s, d: self._copy_file_with_progress(s, d, total_size, copied_size, progress_dialog))
                        else:
                            # 复制单个文件
                            self._copy_file_with_progress(source_path, target_path, total_size, copied_size, progress_dialog)
                    
                    success_count += 1
                
                # 检查是否被取消
                if not progress_dialog.cancelled:
                    # 刷新目标浏览器
                    target_browser.refresh_file_list()
                    # 更新状态栏
                    if skipped_count > 0:
                        self.status_var.set(f"已复制 {success_count} 个项目，跳过 {skipped_count} 个项目")
                    else:
                        self.status_var.set(f"已复制 {success_count} 个项目")
            except OSError as e:
                if not progress_dialog.cancelled:
                    self.status_var.set(f"复制失败: {str(e)}")
                    messagebox.showerror("错误", f"复制失败:\n{str(e)}")
            finally:
                # 关闭进度条对话框
                progress_dialog.destroy()
        
        # 启动复制线程
        copy_thread = threading.Thread(target=copy_task)
        copy_thread.daemon = True
        copy_thread.start()
        
    def move(self):
        """移动多个文件/文件夹，支持冲突处理和全局策略"""
        active_browser = self.get_active_browser()
        if not active_browser:
            return
        
        selected_items = active_browser.tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请选择要移动的文件或文件夹")
            return
        
        # 获取目标浏览器
        if active_browser == self.left_browser:
            target_browser = self.right_browser
        else:
            target_browser = self.left_browser
        
        # 检查是否为SFTP浏览器
        is_source_sftp = hasattr(active_browser, 'is_sftp') and active_browser.is_sftp
        is_target_sftp = hasattr(target_browser, 'is_sftp') and target_browser.is_sftp
        
        print(f"[DEBUG] 移动操作: 源浏览器SFTP={is_source_sftp}, 目标浏览器SFTP={is_target_sftp}")
        import sys
        sys.stdout.flush()
        
        # 准备文件列表
        files_to_move = []
        for item in selected_items:
            # 获取选中项的显示名称
            display_name = active_browser.tree.item(item, 'values')[0]
            
            # 如果是文件夹，移除[]括号
            if display_name.startswith('[') and display_name.endswith(']'):
                actual_name = display_name[1:-1]  # 去掉括号
            else:
                actual_name = display_name
            
            # 构建完整路径
            if is_source_sftp:
                if active_browser.current_path == '/':
                    source_path = f"/{actual_name}"
                else:
                    source_path = f"{active_browser.current_path}/{actual_name}"
            else:
                source_path = os.path.join(active_browser.current_path, actual_name)
            
            if is_target_sftp:
                if target_browser.current_path == '/':
                    target_path = f"/{actual_name}"
                else:
                    target_path = f"{target_browser.current_path}/{actual_name}"
            else:
                target_path = os.path.join(target_browser.current_path, actual_name)
            
            files_to_move.append((source_path, target_path, display_name, is_source_sftp, is_target_sftp))
        
        # 执行移动，处理冲突
        success_count = 0
        skipped_count = 0
        error_files = []
        global_strategy = None  # 全局策略：None, "skip", "replace"
        
        for source_path, target_path, display_name, is_source_sftp, is_target_sftp in files_to_move:
            print(f"[DEBUG] 移动项目: {display_name}")
            print(f"[DEBUG] 源路径: {source_path}, 目标路径: {target_path}")
            sys.stdout.flush()
            
            # 检查文件冲突
            target_exists = False
            if is_target_sftp:
                try:
                    target_exists = target_browser.sftp_fs.exists(target_path)
                except Exception as e:
                    print(f"[ERROR] 检查目标路径失败: {str(e)}")
                    error_files.append(f"{display_name}: 无法检查目标路径 - {str(e)}")
                    continue
            else:
                target_exists = os.path.exists(target_path)
            
            if target_exists:
                # 如果已有全局策略，则直接应用
                if global_strategy == "skip":
                    skipped_count += 1
                    continue
                elif global_strategy == "replace":
                    # 移除目标文件/目录
                    try:
                        if is_target_sftp:
                            if target_browser.sftp_fs.isdir(target_path):
                                # SFTP递归删除目录
                                def sftp_recursive_delete(sftp, path):
                                    for item in sftp.listdir_attr(path):
                                        item_path = f"{path}/{item.filename}"
                                        if stat.S_ISDIR(item.st_mode):
                                            sftp_recursive_delete(sftp, item_path)
                                        else:
                                            sftp.remove(item_path)
                                    sftp.rmdir(path)
                                sftp_recursive_delete(target_browser.sftp_fs.sftp, target_path)
                            else:
                                target_browser.sftp_fs.remove(target_path)
                        else:
                            if os.path.isdir(target_path):
                                shutil.rmtree(target_path)
                            else:
                                os.remove(target_path)
                    except Exception as e:
                        error_files.append(f"{display_name}: 无法删除目标文件 - {str(e)}")
                        continue
                else:
                    # 显示冲突处理对话框
                    conflict_dialog = self.FileConflictDialog(self, display_name, display_name)
                    
                    if conflict_dialog.result == "cancel":
                        # 用户取消整个操作
                        messagebox.showinfo("操作取消", "移动操作已取消")
                        break
                    elif conflict_dialog.result == "skip":
                        # 跳过当前文件
                        skipped_count += 1
                        # 如果用户选择应用到所有，设置全局策略
                        if conflict_dialog.apply_to_all:
                            global_strategy = "skip"
                        continue
                    else:  # replace
                        # 移除目标文件/目录
                        try:
                            if is_target_sftp:
                                if target_browser.sftp_fs.isdir(target_path):
                                    # SFTP递归删除目录
                                    def sftp_recursive_delete(sftp, path):
                                        for item in sftp.listdir_attr(path):
                                            item_path = f"{path}/{item.filename}"
                                            if stat.S_ISDIR(item.st_mode):
                                                sftp_recursive_delete(sftp, item_path)
                                            else:
                                                sftp.remove(item_path)
                                        sftp.rmdir(path)
                                    sftp_recursive_delete(target_browser.sftp_fs.sftp, target_path)
                                else:
                                    target_browser.sftp_fs.remove(target_path)
                            else:
                                if os.path.isdir(target_path):
                                    shutil.rmtree(target_path)
                                else:
                                    os.remove(target_path)
                        except Exception as e:
                            error_files.append(f"{display_name}: 无法删除目标文件 - {str(e)}")
                            continue
                        # 如果用户选择应用到所有，设置全局策略
                        if conflict_dialog.apply_to_all:
                            global_strategy = "replace"
            
            # 执行移动
            try:
                if is_source_sftp and is_target_sftp:
                    # SFTP到SFTP移动
                    print(f"[DEBUG] SFTP到SFTP移动: {source_path} -> {target_path}")
                    active_browser.sftp_fs.rename(source_path, target_path)
                elif is_source_sftp and not is_target_sftp:
                    # SFTP到本地移动（下载）
                    print(f"[DEBUG] SFTP到本地移动: {source_path} -> {target_path}")
                    active_browser.sftp_fs.get(source_path, target_path)
                    active_browser.sftp_fs.remove(source_path)
                elif not is_source_sftp and is_target_sftp:
                    # 本地到SFTP移动（上传）
                    print(f"[DEBUG] 本地到SFTP移动: {source_path} -> {target_path}")
                    target_browser.sftp_fs.put(source_path, target_path)
                    os.remove(source_path)
                else:
                    # 本地到本地移动
                    print(f"[DEBUG] 本地到本地移动: {source_path} -> {target_path}")
                    os.rename(source_path, target_path)
                
                success_count += 1
                print(f"[DEBUG] 移动成功: {display_name}")
                sys.stdout.flush()
            except Exception as e:
                error_msg = f"移动失败: {str(e)}"
                print(f"[ERROR] {error_msg}")
                sys.stdout.flush()
                error_files.append(f"{display_name}: {str(e)}")
        
        # 刷新文件列表
        active_browser.refresh_file_list()
        target_browser.refresh_file_list()
        
        # 显示结果
        status_parts = []
        if success_count > 0:
            status_parts.append(f"已移动 {success_count} 个项目")
        if skipped_count > 0:
            status_parts.append(f"跳过 {skipped_count} 个项目")
        if error_files:
            status_parts.append(f"{len(error_files)} 个失败")
            error_msg = "部分文件移动失败:\n" + "\n".join(error_files)
            messagebox.showerror("移动结果", error_msg)
        
        if status_parts:
            self.status_var.set(", ".join(status_parts))
        else:
            self.status_var.set("移动操作已取消")
    
    class SftpLoginDialog(tk.Toplevel):
        """SFTP登录对话框"""
        def __init__(self, parent):
            super().__init__(parent)
            self.title("SFTP连接")
            self.transient(parent)
            self.resizable(False, False)
            self.geometry("400x300")
            self.parent = parent
            
            # 初始化结果变量
            self.result = None
            
            # 创建内容框架
            content_frame = ttk.Frame(self, padding=15)
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            # 主机名
            ttk.Label(content_frame, text="主机名:").grid(row=0, column=0, sticky=tk.W, pady=5)
            self.host_var = tk.StringVar(value="")
            ttk.Entry(content_frame, textvariable=self.host_var, width=30).grid(row=0, column=1, sticky=tk.W, pady=5)
            
            # 端口
            ttk.Label(content_frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=5)
            self.port_var = tk.StringVar(value="22")
            ttk.Entry(content_frame, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
            
            # 用户名
            ttk.Label(content_frame, text="用户名:").grid(row=2, column=0, sticky=tk.W, pady=5)
            self.username_var = tk.StringVar(value="")
            ttk.Entry(content_frame, textvariable=self.username_var, width=30).grid(row=2, column=1, sticky=tk.W, pady=5)
            
            # 密码
            ttk.Label(content_frame, text="密码:").grid(row=3, column=0, sticky=tk.W, pady=5)
            self.password_var = tk.StringVar(value="")
            self.password_entry = ttk.Entry(content_frame, textvariable=self.password_var, show="*", width=30)
            self.password_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
            
            # 初始目录
            ttk.Label(content_frame, text="初始目录:").grid(row=4, column=0, sticky=tk.W, pady=5)
            self.path_var = tk.StringVar(value="/")
            ttk.Entry(content_frame, textvariable=self.path_var, width=30).grid(row=4, column=1, sticky=tk.W, pady=5)
            
            # 按钮框架
            button_frame = ttk.Frame(content_frame)
            button_frame.grid(row=5, column=0, columnspan=2, pady=15)
            
            # 确认信息按钮
            confirm_btn = ttk.Button(button_frame, text="确认信息", command=self.confirm_connection)
            confirm_btn.pack(side=tk.RIGHT, padx=5)
            
            # 连接按钮
            connect_btn = ttk.Button(button_frame, text="连接", command=self.connect)
            connect_btn.pack(side=tk.RIGHT, padx=5)
            
            # 取消按钮
            cancel_btn = ttk.Button(button_frame, text="取消", command=self.cancel)
            cancel_btn.pack(side=tk.RIGHT, padx=5)
            
            # 绑定回车键到确认按钮
            self.bind('<Return>', lambda e: self.confirm_connection())
            
            # 模态对话框
            self.grab_set()
            self.wait_window(self)
        
        def confirm_connection(self):
            """确认连接信息"""
            # 获取输入值
            host = self.host_var.get().strip()
            port = self.port_var.get().strip()
            username = self.username_var.get().strip()
            password = self.password_var.get()
            path = self.path_var.get().strip()
            
            # 验证输入
            if not host:
                messagebox.showerror("错误", "请输入主机名")
                self.host_var.set("")
                return
            
            if not username:
                messagebox.showerror("错误", "请输入用户名")
                self.username_var.set("")
                return
            
            try:
                port_num = int(port) if port else 22
                if port_num < 1 or port_num > 65535:
                    raise ValueError("端口号必须在1-65535之间")
            except ValueError:
                messagebox.showerror("错误", "请输入有效的端口号")
                self.port_var.set("22")
                return
            
            # 显示确认信息
            auth_info = "密码认证" if password else "无密码认证"
            confirm_message = f"连接信息确认：\n\n"
            confirm_message += f"主机名: {host}\n"
            confirm_message += f"端口: {port_num}\n"
            confirm_message += f"用户名: {username}\n"
            confirm_message += f"认证方式: {auth_info}\n"
            confirm_message += f"初始目录: {path}\n"
            confirm_message += "\n是否确认连接？"
            
            if messagebox.askyesno("确认连接", confirm_message):
                # 用户确认，开始连接
                self.connect()
        
        def connect(self):
            # 获取输入值
            host = self.host_var.get().strip()
            port = self.port_var.get().strip()
            username = self.username_var.get().strip()
            password = self.password_var.get()
            path = self.path_var.get().strip()
            
            # 验证输入
            if not host or not username:
                messagebox.showerror("错误", "主机名和用户名不能为空")
                return
            
            try:
                port = int(port)
                if port < 1 or port > 65535:
                    raise ValueError("端口号必须在1-65535之间")
            except ValueError:
                messagebox.showerror("错误", "请输入有效的端口号")
                return
            
            # 设置结果并关闭对话框
            self.result = {
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'path': path
            }
            self.destroy()
        
        def cancel(self):
            self.result = None
            self.destroy()
    
    def open_sftp_dialog(self):
        """打开SFTP登录对话框"""
        if not HAS_PARAMIKO:
            messagebox.showerror("错误", "SFTP功能需要paramiko库。请运行 'pip install paramiko' 安装")
            return
        
        # 获取活动浏览器
        active_browser = self.get_active_browser()
        if not active_browser:
            messagebox.showinfo("提示", "请先激活一个浏览器窗口")
            return
        
        # 显示登录对话框
        dialog = self.SftpLoginDialog(self)
        
        # 如果用户点击了连接
        if dialog.result:
            # 在后台线程中连接SFTP
            threading.Thread(target=self.connect_to_sftp, args=(active_browser, dialog.result)).start()
    
    def connect_to_sftp(self, browser, sftp_info):
        """连接到SFTP服务器并显示文件列表"""
        # 更新状态栏显示连接中
        self.status_var.set(f"正在连接到 {sftp_info['host']}...")
        
        try:
            # 创建SSH客户端
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接到服务器
            ssh.connect(
                hostname=sftp_info['host'],
                port=sftp_info['port'],
                username=sftp_info['username'],
                password=sftp_info['password']
            )
            
            # 创建SFTP客户端
            sftp = ssh.open_sftp()
            
            # 检查路径是否存在
            try:
                sftp.stat(sftp_info['path'])
            except FileNotFoundError:
                self.after(0, messagebox.showerror, "错误", f"路径不存在: {sftp_info['path']}")
                sftp.close()
                ssh.close()
                self.after(0, lambda: self.status_var.set("连接失败"))
                return
            
            # 创建SFTP文件系统对象
            sftp_fs = SftpFileSystem(ssh, sftp, sftp_info)
            
            # 更新浏览器使用SFTP文件系统
            self.after(0, lambda: self._update_browser_for_sftp(browser, sftp_fs))
            
        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            self.after(0, messagebox.showerror, "错误", error_msg)
            self.after(0, lambda: self.status_var.set("连接失败"))
    
    def _update_browser_for_sftp(self, browser, sftp_fs):
        """更新浏览器以使用SFTP文件系统"""
        try:
            # 保存原始方法
            browser._original_refresh = browser.refresh_file_list
            browser._original_open_file = browser.open_file
            browser._original_delete_press = browser.on_delete_press
            browser._original_sort_by_column = browser.sort_by_column if hasattr(browser, 'sort_by_column') else None
            
            # 替换为SFTP版本的方法
            browser.refresh_file_list = lambda: self._sftp_refresh_file_list(browser, sftp_fs)
            # 保留原始的navigate_to方法，但在其中添加SFTP支持
            browser.open_file = lambda path: self._sftp_open_file(browser, sftp_fs, path)
            browser.on_delete_press = lambda event: self._sftp_on_delete_press(browser, sftp_fs, event)
            browser.sort_by_column = lambda column: self._sftp_sort_by_column(browser, sftp_fs, column)
            
            # 初始化历史记录
            browser.history = []
            browser.history_index = -1
            
            # 设置SFTP标志和当前路径
            browser.is_sftp = True
            browser.sftp_fs = sftp_fs
            browser.current_path = sftp_fs.initial_path
            
            # 刷新文件列表
            browser.refresh_file_list()
            
            # 更新状态栏
            self.status_var.set(f"已连接到 {sftp_fs.host}:{sftp_fs.initial_path}")
        except Exception as e:
            error_msg = f"初始化SFTP浏览器失败: {str(e)}"
            self.after(0, messagebox.showerror, "错误", error_msg)
            self.after(0, lambda: self.status_var.set(f"错误: {str(e)}"))
            
            # 恢复原始方法
            if hasattr(browser, '_original_refresh'):
                browser.refresh_file_list = browser._original_refresh
                browser.open_file = browser._original_open_file
                browser.on_delete_press = browser._original_delete_press
                if browser._original_sort_by_column:
                    browser.sort_by_column = browser._original_sort_by_column
                browser.is_sftp = False
                if hasattr(browser, 'sftp_fs'):
                    delattr(browser, 'sftp_fs')
    
    def _sftp_refresh_file_list(self, browser, sftp_fs):
        """SFTP版本的刷新文件列表方法"""
        # 清空当前列表
        for item in browser.tree.get_children():
            browser.tree.delete(item)
        
        # 更新路径显示
        browser.path_var.set(f"sftp://{sftp_fs.username}@{sftp_fs.host}:{sftp_fs.port}{browser.current_path}")
        
        try:
            # 获取文件列表
            items = sftp_fs.listdir(browser.current_path)
            
            # 分离文件夹和文件
            folders = []
            files = []
            
            for item in items:
                # 跳过隐藏文件（除非设置了显示隐藏文件）
                if not browser.show_hidden and item.startswith('.'):
                    continue
                
                path = sftp_fs.join(browser.current_path, item)
                if sftp_fs.isdir(path):
                    folders.append(item)
                else:
                    files.append(item)
            
            # 排序
            folders.sort()
            files.sort()
            
            # 添加到视图
            for folder in folders:
                path = sftp_fs.join(browser.current_path, folder)
                try:
                    stat_info = sftp_fs.stat(path)
                    size = ""
                    modified = time.ctime(stat_info.st_mtime)
                    # 在文件夹名称两边添加[]，并应用folder标签
                    browser.tree.insert('', tk.END, values=(f'[{folder}]', '文件夹', size, modified), tags=('folder',))
                except Exception:
                    browser.tree.insert('', tk.END, values=(f'[{folder}]', '文件夹', '', ''), tags=('folder',))
            
            for file in files:
                path = sftp_fs.join(browser.current_path, file)
                try:
                    stat_info = sftp_fs.stat(path)
                    size = browser.format_size(stat_info.st_size)
                    modified = time.ctime(stat_info.st_mtime)
                    # 获取文件类型
                    file_type = browser.get_file_type(file)
                    browser.tree.insert('', tk.END, values=(file, file_type, size, modified), tags=('file',))
                except Exception:
                    browser.tree.insert('', tk.END, values=(file, '', '', ''), tags=('file',))
            
            # 更新状态栏
            total_items = len(folders) + len(files)
            hidden_status = "(显示隐藏文件)" if browser.show_hidden else ""
            browser.status_var.set(f'{total_items} 个项目 {hidden_status}')
            
        except Exception as e:
            browser.status_var.set(f'错误: {str(e)}')
    
    def _sftp_sort_by_column(self, browser, sftp_fs, column):
        """SFTP版本的按列排序文件列表"""
        # 获取当前所有项目
        items = list(browser.tree.get_children())
        if not items:
            return
        
        # 获取当前排序状态
        current_heading = browser.tree.heading(column)
        current_text = current_heading['text']
        
        # 判断当前排序方向并切换
        if current_text.endswith(' ▼'):
            # 当前是降序，切换到升序
            reverse = False
            new_text = current_text.replace(' ▼', ' ▲')
        elif current_text.endswith(' ▲'):
            # 当前是升序，切换到降序
            reverse = True
            new_text = current_text.replace(' ▲', ' ▼')
        else:
            # 首次点击，默认升序
            reverse = False
            new_text = current_text + ' ▲'
        
        # 更新表头文本
        browser.tree.heading(column, text=new_text)
        
        # 重置其他列的表头文本（移除排序指示器）
        for col in ['name', 'type', 'size', 'modified']:
            if col != column:
                current_col_text = browser.tree.heading(col)['text']
                if current_col_text.endswith(' ▲') or current_col_text.endswith(' ▼'):
                    base_text = current_col_text.replace(' ▲', '').replace(' ▼', '')
                    browser.tree.heading(col, text=base_text)
        
        # 分离文件夹和文件
        folders = []
        files = []
        
        for item in items:
            values = browser.tree.item(item, 'values')
            if values[1] == '文件夹':
                folders.append((item, values))
            else:
                files.append((item, values))
        
        # 排序函数
        def get_sort_key(item_data):
            item, values = item_data
            col_index = ['name', 'type', 'size', 'modified'].index(column)
            value = values[col_index]
            
            if column == 'name':
                # 名称排序：去掉文件夹的[]符号
                name = values[0]
                if name.startswith('[') and name.endswith(']'):
                    name = name[1:-1]  # 去掉括号
                return name.lower()
            elif column == 'size':
                # 大小排序：转换为字节数
                size_str = value
                if not size_str:
                    return 0
                # 解析大小字符串
                if 'GB' in size_str:
                    return float(size_str.replace(' GB', '')) * 1024 * 1024 * 1024
                elif 'MB' in size_str:
                    return float(size_str.replace(' MB', '')) * 1024 * 1024
                elif 'KB' in size_str:
                    return float(size_str.replace(' KB', '')) * 1024
                elif 'B' in size_str:
                    return float(size_str.replace(' B', ''))
                else:
                    return 0
            elif column == 'modified':
                # 修改日期排序：转换为时间戳
                try:
                    import time
                    return time.mktime(time.strptime(value))
                except:
                    return 0
            else:
                # 类型或其他列：直接按字符串排序
                return value.lower()
        
        # 分别排序文件夹和文件
        folders.sort(key=get_sort_key, reverse=reverse)
        files.sort(key=get_sort_key, reverse=reverse)
        
        # 清空当前列表
        for item in items:
            browser.tree.delete(item)
        
        # 重新插入项目（先文件夹后文件）
        for item, values in folders:
            browser.tree.insert('', tk.END, values=values, tags=('folder',))
        
        for item, values in files:
            browser.tree.insert('', tk.END, values=values, tags=('file',))
    
    def _sftp_navigate_to(self, browser, sftp_fs, path):
        """SFTP版本的导航方法"""
        try:
            # 处理不同情况的路径
            if path.startswith('sftp://'):
                # 如果是完整的SFTP URL，提取路径部分
                # 格式: sftp://username@host:port/path
                import re
                match = re.match(r'sftp://[^/]+(/.*)', path)
                if match:
                    path = match.group(1)
                else:
                    path = '/'  # 默认为根目录
            elif not path.startswith('/'):
                # 如果是相对路径，从当前路径构建绝对路径
                path = sftp_fs.join(browser.current_path, path)
            
            # 规范化路径（去除../和./）
            path_parts = []
            for part in path.split('/'):
                if part == '..':
                    if path_parts:  # 确保不会删除根路径
                        path_parts.pop()
                elif part and part != '.':
                    path_parts.append(part)
            
            # 重新构建规范化后的路径
            if not path_parts:  # 空路径表示根目录
                path = '/'
            else:
                path = '/' + '/'.join(path_parts)
            
            # 检查路径是否存在且是目录
            if sftp_fs.exists(path) and sftp_fs.isdir(path):
                # 保存历史记录
                if not hasattr(browser, 'history'):
                    browser.history = []
                    browser.history_index = -1
                
                # 如果当前不在历史记录末尾，清除后面的记录
                if browser.history_index < len(browser.history) - 1:
                    browser.history = browser.history[:browser.history_index + 1]
                
                # 添加当前路径到历史记录
                if browser.current_path != path:
                    browser.history.append(browser.current_path)
                    browser.history_index += 1
                
                # 更新当前路径
                browser.current_path = path
                browser.refresh_file_list()
                
                # 启用/禁用前进后退按钮
                browser.back_btn['state'] = 'normal' if browser.history_index >= 0 else 'disabled'
                browser.forward_btn['state'] = 'normal' if browser.history_index < len(browser.history) - 1 else 'disabled'
                
                # 通知父窗口路径变化
                if hasattr(browser, 'on_path_change') and browser.on_path_change:
                    browser.on_path_change(path)
            else:
                # 路径不存在或不是目录
                self.after(0, messagebox.showerror, "导航错误", f"无法导航到 '{path}'。路径不存在或不是目录。")
                browser.status_var.set(f"导航错误: 路径不存在或不是目录")
        except Exception as e:
            # 捕获所有异常并显示错误信息
            error_msg = f"导航失败: {str(e)}"
            self.after(0, messagebox.showerror, "导航错误", error_msg)
            browser.status_var.set(f"错误: {str(e)}")
    
    def _sftp_open_file(self, browser, sftp_fs, path):
        """SFTP版本的打开文件方法"""
        try:
            # 创建临时目录
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            # 创建临时文件
            local_path = os.path.join(temp_dir, os.path.basename(path))
            
            # 下载文件到本地临时目录
            sftp_fs.get(path, local_path)
            
            # 使用默认程序打开文件
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', local_path])
            elif sys.platform == 'win32':  # Windows
                os.startfile(local_path)
            else:  # Linux
                subprocess.run(['xdg-open', local_path])
                
        except Exception as e:
            messagebox.showerror('打开文件失败', str(e))
    
    def _sftp_on_delete_press(self, browser, sftp_fs, event):
        """SFTP版本的删除方法 - 处理单个项目删除"""
        # 强制刷新标准输出，确保调试信息能显示
        import sys
        sys.stdout.flush()
        
        selected = browser.tree.selection()
        if not selected:
            print("[DEBUG] 没有选中任何项目")
            return
            
        # 只处理第一个选中的项目（保持与事件处理的一致性）
        display_name = browser.tree.item(selected[0], 'values')[0]
        print(f"[DEBUG] 开始删除操作，显示名称: {display_name}")
        sys.stdout.flush()
        
        # 如果是文件夹，移除[]括号
        name = display_name
        if name.startswith('[') and name.endswith(']'):
            name = name[1:-1]
        
        # 构建完整路径，确保使用正确的路径分隔符
        if browser.current_path == '/':
            path = f"/{name}"
        else:
            path = f"{browser.current_path}/{name}"
        
        print(f"[DEBUG] 当前路径: {browser.current_path}")
        print(f"[DEBUG] 构建的完整路径: {path}")
        sys.stdout.flush()
        
        # 判断是否为目录
        is_dir = False
        try:
            is_dir = sftp_fs.isdir(path)
            print(f"[DEBUG] 路径类型检查: is_dir = {is_dir}")
            sys.stdout.flush()
        except Exception as e:
            error_msg = f"无法访问路径 {path}: {str(e)}"
            print(f"[ERROR] {error_msg}")
            sys.stdout.flush()
            messagebox.showerror('错误', error_msg)
            return
        
        # 显示确认消息
        if is_dir:
            # 检查目录是否为空
            try:
                items = sftp_fs.listdir(path)
                is_empty = len(items) == 0
                print(f"[DEBUG] 目录检查: 项目数量 = {len(items)}, 是否为空 = {is_empty}")
                sys.stdout.flush()
                if not is_empty:
                    confirm_msg = f"确定要删除目录 '{display_name}' 及其所有内容吗？此操作不可撤销！"
                else:
                    confirm_msg = f"确定要删除目录 '{display_name}' 吗？此操作不可撤销！"
            except Exception as e:
                error_msg = f"检查目录内容失败: {str(e)}"
                print(f"[ERROR] {error_msg}")
                sys.stdout.flush()
                confirm_msg = f"确定要删除目录 '{display_name}' 吗？此操作不可撤销！"
        else:
            confirm_msg = f"确定要删除 {display_name} 吗？"
        
        if messagebox.askyesno('确认删除', confirm_msg):
            try:
                if is_dir:
                    print(f"[DEBUG] 开始递归删除目录: {path}")
                    sys.stdout.flush()
                    # 递归删除目录及其内容
                    def sftp_recursive_delete(sftp, current_path):
                        print(f"[DEBUG] 递归删除: 进入目录 {current_path}")
                        sys.stdout.flush()
                        try:
                            items = sftp.listdir_attr(current_path)
                            print(f"[DEBUG] 目录 {current_path} 包含 {len(items)} 个项目")
                            sys.stdout.flush()
                            
                            for item in items:
                                item_name = item.filename
                                item_path = f"{current_path}/{item_name}"
                                print(f"[DEBUG] 处理项目: {item_name}, 路径: {item_path}")
                                sys.stdout.flush()
                                
                                # 检查是否为目录
                                if item.st_mode & 0o40000:  # 目录权限位
                                    print(f"[DEBUG] 项目 {item_name} 是目录，递归删除")
                                    sys.stdout.flush()
                                    sftp_recursive_delete(sftp, item_path)
                                else:
                                    # 删除文件
                                    try:
                                        print(f"[DEBUG] 删除文件: {item_path}")
                                        sys.stdout.flush()
                                        sftp.remove(item_path)
                                        print(f"[DEBUG] 文件删除成功: {item_path}")
                                        sys.stdout.flush()
                                    except Exception as e:
                                        error_msg = f"删除文件失败: {item_path}, 错误: {str(e)}"
                                        print(f"[ERROR] {error_msg}")
                                        sys.stdout.flush()
                                        raise Exception(error_msg)
                            
                            # 删除空目录
                            print(f"[DEBUG] 删除空目录: {current_path}")
                            sys.stdout.flush()
                            sftp.rmdir(current_path)
                            print(f"[DEBUG] 目录删除成功: {current_path}")
                            sys.stdout.flush()
                            
                        except Exception as e:
                            error_msg = f"删除目录失败: {current_path}, 错误: {str(e)}"
                            print(f"[ERROR] {error_msg}")
                            sys.stdout.flush()
                            raise Exception(error_msg)
                    
                    # 执行递归删除
                    sftp_recursive_delete(sftp_fs.sftp, path)
                    print(f"[DEBUG] 目录递归删除完成: {path}")
                    sys.stdout.flush()
                else:
                    # 删除文件
                    print(f"[DEBUG] 删除文件: {path}")
                    sys.stdout.flush()
                    try:
                        sftp_fs.remove(path)
                        print(f"[DEBUG] 文件删除成功: {path}")
                        sys.stdout.flush()
                    except FileNotFoundError:
                        error_msg = f"文件不存在: {path}"
                        print(f"[ERROR] {error_msg}")
                        sys.stdout.flush()
                        messagebox.showinfo('提示', f'文件不存在: {display_name}')
                        return
                    except Exception as e:
                        error_msg = f"删除文件失败: {path}, 错误: {str(e)}"
                        print(f"[ERROR] {error_msg}")
                        sys.stdout.flush()
                        raise Exception(error_msg)
                
                # 刷新文件列表
                print(f"[DEBUG] 刷新文件列表")
                sys.stdout.flush()
                browser.refresh_file_list()
                messagebox.showinfo('成功', f'删除成功: {display_name}')
                print(f"[DEBUG] 删除操作完成: {display_name}")
                sys.stdout.flush()
                
            except Exception as e:
                error_msg = f"删除操作失败: {str(e)}"
                print(f"[ERROR] {error_msg}")
                sys.stdout.flush()
                messagebox.showerror('删除失败', error_msg)
    
    def _sftp_delete_multiple(self, browser, sftp_fs, selected_items):
        """SFTP版本的多选删除方法"""
        import sys
        sys.stdout.flush()
        
        if not selected_items:
            print("[DEBUG] 没有选中任何项目")
            return
        
        print(f"[DEBUG] 开始多选删除操作，选中 {len(selected_items)} 个项目")
        sys.stdout.flush()
        
        # 准备文件列表
        items_to_delete = []
        has_non_empty_dir = False
        
        for item in selected_items:
            # 获取选中项的显示名称
            display_name = browser.tree.item(item, "values")[0]
            
            # 处理带括号的文件夹名称
            if display_name.startswith('[') and display_name.endswith(']'):
                actual_name = display_name[1:-1]  # 去掉括号
            else:
                actual_name = display_name
            
            # 构建完整路径
            if browser.current_path == '/':
                path = f"/{actual_name}"
            else:
                path = f"{browser.current_path}/{actual_name}"
            
            # 判断是否为目录
            is_dir = False
            try:
                is_dir = sftp_fs.isdir(path)
                print(f"[DEBUG] 项目 {actual_name} 类型检查: is_dir = {is_dir}")
                sys.stdout.flush()
            except Exception as e:
                print(f"[ERROR] 无法访问路径 {path}: {str(e)}")
                sys.stdout.flush()
                continue
            
            items_to_delete.append((path, display_name, is_dir))
            
            # 检查是否有非空目录
            if is_dir:
                try:
                    items = sftp_fs.listdir(path)
                    if len(items) > 0:
                        has_non_empty_dir = True
                except Exception:
                    pass
        
        if not items_to_delete:
            messagebox.showinfo("提示", "没有有效的项目可以删除")
            return
        
        # 根据选择数量和内容显示确认消息
        if len(items_to_delete) == 1:
            path, display_name, is_dir = items_to_delete[0]
            if is_dir:
                try:
                    items = sftp_fs.listdir(path)
                    if len(items) > 0:
                        confirm_msg = f"确定要删除目录 '{display_name}' 及其所有内容吗？此操作不可撤销！"
                    else:
                        confirm_msg = f"确定要删除目录 '{display_name}' 吗？此操作不可撤销！"
                except Exception:
                    confirm_msg = f"确定要删除目录 '{display_name}' 吗？此操作不可撤销！"
            else:
                confirm_msg = f"确定要删除 '{display_name}' 吗？"
        else:
            if has_non_empty_dir:
                confirm_msg = f"确定要删除选中的 {len(items_to_delete)} 个项目（包含非空目录）及其所有内容吗？此操作不可撤销！"
            else:
                confirm_msg = f"确定要删除选中的 {len(items_to_delete)} 个项目吗？"
        
        # 确认删除
        response = messagebox.askyesno("确认删除", confirm_msg)
        if response:
            success_count = 0
            error_files = []
            
            for path, display_name, is_dir in items_to_delete:
                try:
                    if is_dir:
                        print(f"[DEBUG] 开始递归删除目录: {path}")
                        sys.stdout.flush()
                        # 递归删除目录及其内容
                        def sftp_recursive_delete(sftp, current_path):
                            print(f"[DEBUG] 递归删除: 进入目录 {current_path}")
                            sys.stdout.flush()
                            try:
                                items = sftp.listdir_attr(current_path)
                                print(f"[DEBUG] 目录 {current_path} 包含 {len(items)} 个项目")
                                sys.stdout.flush()
                                
                                for item in items:
                                    item_name = item.filename
                                    item_path = f"{current_path}/{item_name}"
                                    print(f"[DEBUG] 处理项目: {item_name}, 路径: {item_path}")
                                    sys.stdout.flush()
                                    
                                    # 检查是否为目录
                                    if item.st_mode & 0o40000:  # 目录权限位
                                        print(f"[DEBUG] 项目 {item_name} 是目录，递归删除")
                                        sys.stdout.flush()
                                        sftp_recursive_delete(sftp, item_path)
                                    else:
                                        # 删除文件
                                        try:
                                            print(f"[DEBUG] 删除文件: {item_path}")
                                            sys.stdout.flush()
                                            sftp.remove(item_path)
                                            print(f"[DEBUG] 文件删除成功: {item_path}")
                                            sys.stdout.flush()
                                        except Exception as e:
                                            error_msg = f"删除文件失败: {item_path}, 错误: {str(e)}"
                                            print(f"[ERROR] {error_msg}")
                                            sys.stdout.flush()
                                            raise Exception(error_msg)
                                
                                # 删除空目录
                                print(f"[DEBUG] 删除空目录: {current_path}")
                                sys.stdout.flush()
                                sftp.rmdir(current_path)
                                print(f"[DEBUG] 目录删除成功: {current_path}")
                                sys.stdout.flush()
                                
                            except Exception as e:
                                error_msg = f"删除目录失败: {current_path}, 错误: {str(e)}"
                                print(f"[ERROR] {error_msg}")
                                sys.stdout.flush()
                                raise Exception(error_msg)
                        
                        # 执行递归删除
                        sftp_recursive_delete(sftp_fs.sftp, path)
                        print(f"[DEBUG] 目录递归删除完成: {path}")
                        sys.stdout.flush()
                    else:
                        # 删除文件
                        print(f"[DEBUG] 删除文件: {path}")
                        sys.stdout.flush()
                        try:
                            sftp_fs.remove(path)
                            print(f"[DEBUG] 文件删除成功: {path}")
                            sys.stdout.flush()
                        except FileNotFoundError:
                            error_msg = f"文件不存在: {path}"
                            print(f"[ERROR] {error_msg}")
                            sys.stdout.flush()
                            error_files.append(f"{display_name}: 文件不存在")
                            continue
                        except Exception as e:
                            error_msg = f"删除文件失败: {path}, 错误: {str(e)}"
                            print(f"[ERROR] {error_msg}")
                            sys.stdout.flush()
                            error_files.append(f"{display_name}: {str(e)}")
                            continue
                    
                    success_count += 1
                    
                except Exception as e:
                    error_msg = f"删除失败: {display_name}, 错误: {str(e)}"
                    print(f"[ERROR] {error_msg}")
                    sys.stdout.flush()
                    error_files.append(f"{display_name}: {str(e)}")
            
            # 刷新文件列表
            print(f"[DEBUG] 刷新文件列表")
            sys.stdout.flush()
            browser.refresh_file_list()
            
            # 显示结果
            if error_files:
                error_msg = f"已删除 {success_count} 个项目，{len(error_files)} 个失败:\n" + "\n".join(error_files)
                messagebox.showerror("删除结果", error_msg)
            else:
                messagebox.showinfo("成功", f"已删除 {success_count} 个项目")
    
    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo('关于', '双窗口文件浏览器\n\n版本: 1.0\n模仿macOS Finder的双窗口文件浏览器')

# 导入必要的模块
import time
import stat

class SftpFileSystem:
    """SFTP文件系统包装类，提供类似os模块的接口"""
    def __init__(self, ssh, sftp, sftp_info):
        self.ssh = ssh
        self.sftp = sftp
        self.host = sftp_info['host']
        self.port = sftp_info['port']
        self.username = sftp_info['username']
        self.initial_path = sftp_info['path']
    
    def listdir(self, path):
        """列出目录内容"""
        return self.sftp.listdir(path)
    
    def exists(self, path):
        """检查路径是否存在"""
        try:
            self.sftp.stat(path)
            return True
        except FileNotFoundError:
            return False
    
    def isdir(self, path):
        """检查是否为目录"""
        try:
            stat = self.sftp.stat(path)
            # 在Unix系统中，目录的权限的第一位是d，对应的st_mode的S_IFDIR位会被设置
            import stat as stat_module
            return stat.st_mode & stat_module.S_IFDIR
        except Exception:
            return False
    
    def isfile(self, path):
        """检查是否为文件"""
        try:
            stat = self.sftp.stat(path)
            import stat as stat_module
            return stat.st_mode & stat_module.S_IFREG
        except Exception:
            return False
    
    def stat(self, path):
        """获取文件状态"""
        return self.sftp.stat(path)
    
    def join(self, path1, path2):
        """连接路径"""
        # 确保路径正确连接
        if path1.endswith('/'):
            return path1 + path2
        else:
            return path1 + '/' + path2
    
    def get(self, remote_path, local_path):
        """下载文件"""
        self.sftp.get(remote_path, local_path)
    
    def put(self, local_path, remote_path):
        """上传文件"""
        self.sftp.put(local_path, remote_path)
    
    def remove(self, path):
        """删除文件"""
        self.sftp.remove(path)
    
    def rmdir(self, path):
        """删除目录（必须为空）"""
        # 检查目录是否为空
        if len(self.sftp.listdir(path)) > 0:
            raise OSError("目录不为空")
        self.sftp.rmdir(path)
    
    def mkdir(self, path):
        """创建目录"""
        self.sftp.mkdir(path)
    
    def rename(self, oldpath, newpath):
        """重命名文件或目录"""
        self.sftp.rename(oldpath, newpath)
    
    def copy(self, source_path, target_path):
        """在SFTP服务器上复制文件"""
        # 对于SFTP，我们需要先读取源文件，然后写入目标文件
        # 这是因为paramiko的SFTP客户端没有直接的copy方法
        with self.sftp.open(source_path, 'rb') as source_file:
            with self.sftp.open(target_path, 'wb') as target_file:
                # 使用缓冲区进行复制
                chunk_size = 8192
                while True:
                    data = source_file.read(chunk_size)
                    if not data:
                        break
                    target_file.write(data)
    
    def close(self):
        """关闭连接"""
        self.sftp.close()
        self.ssh.close()

# 主函数
def main():
    # 创建应用实例
    app = FinderBrowser()
    
    # 运行主循环
    app.mainloop()

if __name__ == "__main__":
    main()