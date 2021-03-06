# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
from PyQt4 import Qt

import magic
import os
import operator
import platform
import re  # for regex
import socket
import sys
import threading
import time
import xml.etree.cElementTree as ET
from PyQt4 import QtCore, QtGui



import pycountry
import requests
import storj
from PyQt4.QtCore import QAbstractTableModel, SIGNAL
from PyQt4.QtCore import QVariant
from PyQt4.QtGui import *
from ipwhois import IPWhois
from lxml import etree
from storj import exception
from storj import model

import pingparser
from bucket_manage_ui import Ui_BucketManager
from client_configuration_ui import Ui_ClientConfiguration
from create_bucket_ui import Ui_BucketCreate
from file_crypto_tools import FileCrypto  # file ancryption and decryption lib
from file_manager_ui import Ui_FileManager
from file_mirrors_list_ui import Ui_FileMirrorsList
from initial_window_ui import Ui_InitialWindow
from main_menu_ui import Ui_MainMenu
from node_details_ui import Ui_NodeDetails
from single_file_downloader_ui import Ui_SingleFileDownload
from single_file_upload_ui import Ui_SingleFileUpload
from storj_login_ui import Ui_Login
from storj_register_ui import Ui_Register

from sharder import ShardingTools

# ext libs

# Define CONSTANS


global html_format_begin, html_format_end
html_format_begin = "<html><head/><body><p><span style=\" font-size:12pt; font-weight:600;\">"
html_format_end = "</span></p></body></html>"



class ProgressBar(QProgressBar):

    def __init__(self, value, parent=None):
        QProgressBar.__init__(self)
        self.setMinimum(1)
        self.setMaximum(100)
        self.setValue(value)
        self.setFormat('{0:.5f}'.format(value))
        #style = ''' QProgressBar{max-height: 15px;text-align: center;}'''
        #self.setStyleSheet(style)

class ProgressWidgetItem(QTableWidgetItem):

    def __lt__(self, other):
        return self.data(Qt.UserRole) < other.data(Qt.UserRole)

    def updateValue(self, value):
        self.setData(Qt.UserRole, value)

class Tools():
    def check_email(self, email):
        if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email):
            return False
        else:
            return True

    def measure_ping_latency(self, destination_host):
        ping_latency = str(os.system(
            "ping " + ("-n 1 " if platform.system().lower() == "windows" else "-c 1 ") + str(destination_host)))

        ping_data_parsed = pingparser.parse(ping_latency)

        return ping_data_parsed

    def human_size(self, size_bytes):
        """
        format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
        Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
        e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
        From: <http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size>
        """
        if size_bytes == 1:
            # because I really hate unnecessary plurals
            return "1 byte"

        suffixes_table = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

        num = float(size_bytes)
        for suffix, precision in suffixes_table:
            if num < 1024.0:
                break
            num /= 1024.0

        if precision == 0:
            formatted_size = "%d" % num
        else:
            formatted_size = str(round(num, ndigits=precision))

        return "%s %s" % (formatted_size, suffix)


class MyTableModel(QtCore.QAbstractTableModel):
    def __init__(self,data,parent=None):
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.__data=data     # Initial Data

    def rowCount( self, parent ):
        return len(self.__data)

    def columnCount( self , parent ):
        return len(self.__data)

    def data ( self , index , role ):
        if role == QtCore.Qt.DisplayRole:
            row = index.row()
            column = index.column()
            value = self.__data[row][column]
            return QtCore.QString(str(value))

    def setData(self, index, value):
        self.__data[index.row()][index.column()] = value
        return True

    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsSelectable

    def insertRows(self , position , rows , item , parent=QtCore.QModelIndex()):
        # beginInsertRows (self, QModelIndex parent, int first, int last)
        self.beginInsertRows(QtCore.QModelIndex(),len(self.__data),len(self.__data)+1)
        self.__data.append(item) # Item must be an array
        self.endInsertRows()
        return True


# Configuration backend section
class Configuration():
    def __init__(
            self, sameFileNamePrompt=None, sameFileHashPrompt=None, load_config=False
    ):

        if load_config:

            et = None

            try:
                et = etree.parse("storj_client_config.xml")
            except:
                print "Unspecified XML parse error"

            for tags in et.iter(str("same_file_name_prompt")):
                if tags.text == "1":
                    self.sameFileNamePrompt = True
                elif tags.text == "0":
                    self.sameFileNamePrompt = False
                else:
                    self.sameFileNamePrompt = True
            for tags in et.iter(str("same_file_hash_prompt")):
                if tags.text == "1":
                    self.sameFileHashPrompt = True
                elif tags.text == "0":
                    self.sameFileHashPrompt = False
                else:
                    self.sameFileHashPrompt = True
            for tags in et.iter(str("max_chunk_size_for_download")):
                if tags.text != None:
                    self.maxDownloadChunkSize = int(tags.text)
                else:
                    self.maxDownloadChunkSize = 1024


    def get_config_parametr_value(self, parametr):
        output = ""
        try:
            et = etree.parse("storj_client_config.xml")
            for tags in et.iter(str(parametr)):
                output = tags.text
        except:
            print "Unspecified error"

        return output

    def load_config_from_xml(self):
        try:
            et = etree.parse("storj_client_config.xml")
            for tags in et.iter('password'):
                output = tags.text
        except:
            print "Unspecified error"

    def save_client_configuration(self, settings_ui):
        root = ET.Element("configuration")
        doc = ET.SubElement(root, "client")
        i = 0

        # settings_ui = Ui_
        ET.SubElement(doc, "max_shard_size").text = str("")
        ET.SubElement(doc, "max_connections_onetime").text = str("test")
        ET.SubElement(doc, "advanced_view_enabled").text = str("test")
        ET.SubElement(doc, "max_download_bandwith").text = str("test")
        ET.SubElement(doc, "max_upload_bandwith").text = str("test")
        ET.SubElement(doc, "default_file_encryption_algorithm").text = str("AES")
        tree = ET.ElementTree(root)
        tree.write("storj_client_config.xml")


class AccountManager():
    def __init__(self, login_email=None, password=None):
        self.login_email = login_email
        self.password = password

    def save_account_credentials(self):
        root = ET.Element("account")
        doc = ET.SubElement(root, "credentials")
        i = 0

        ET.SubElement(doc, "login_email").text = str(self.login_email)
        ET.SubElement(doc, "password").text = str(self.password)
        ET.SubElement(doc, "logged_in").text = str("1")
        tree = ET.ElementTree(root)
        tree.write("storj_account_conf.xml")

    def if_logged_in(self):
        logged_in = "0"
        try:
            et = etree.parse("storj_account_conf.xml")
            for tags in et.iter('logged_in'):
                logged_in = tags.text
        except:
            logged_in = "0"
            print "Unspecified error"

        if logged_in == "1":
            return True
        else:
            return False

    def logout(self):
        print  1

    def get_user_password(self):
        password = ""
        try:
            et = etree.parse("storj_account_conf.xml")
            for tags in et.iter('password'):
                password = tags.text
        except:
            print "Unspecified error"
        return password

    def get_user_email(self):
        email = ""
        try:
            et = etree.parse("storj_account_conf.xml")
            for tags in et.iter('login_email'):
                email = tags.text
        except:
            print "Unspecified error"
        return email
        print 1


# Configuration Ui section
class ClientConfigurationUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        # register UI
        self.client_configuration_ui = Ui_ClientConfiguration()
        self.client_configuration_ui.setupUi(self)

        self.configuration_manager = Configuration()

        QtCore.QObject.connect(self.client_configuration_ui.apply_bt, QtCore.SIGNAL("clicked()"),
                               self.save_settings)  # valudate and register user

    def save_settings(self):
        # validate settings

        self.configuration_manager.save_client_configuration(self.client_configuration_ui)  # save configuration

    def reset_settings_to_default(self):
        print 1


# Register section
class RegisterUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        # register UI
        self.register_ui = Ui_Register()
        self.register_ui.setupUi(self)

        self.register_ui.password.setEchoMode(QLineEdit.Password)
        self.register_ui.password_2.setEchoMode(QLineEdit.Password)

        QtCore.QObject.connect(self.register_ui.register_bt, QtCore.SIGNAL("clicked()"),
                               self.register)  # valudate and register user

    def register(self):
        # validate fields


        self.email = self.register_ui.email.text()
        self.password = self.register_ui.password.text()
        self.password_repeat = self.register_ui.password_2.text()

        self.tools = Tools()
        success = False
        if self.email != "" and self.password != "" and self.password_repeat != "":
            if self.password == self.password_repeat:
                if (self.tools.check_email(self.email)):
                    # take login action
                    try:
                        self.storj_client = storj.Client(str(self.email), str(self.password))
                        print self.email
                        success = True
                        # self.storj_client.user_create("wiktest15@gmail.com", "kotek1")
                    except storj.exception.StorjBridgeApiError, e:
                        j = json.loads(str(e))
                        if (j["error"] == "Email is already registered"):
                            success = False
                            QMessageBox.about(self, "Warning",
                                              "User with this e-mail is already registered! Please login or try different e-mail!")
                        else:
                            success = False
                            QMessageBox.about(self, "Unhandled exception", "Exception: " + str(e))
                else:
                    success = False
                    QMessageBox.about(self, "Warning",
                                      "Your e-mail seems to be invalid! Please chech e-mail  and try again")
            else:
                success = False
                QMessageBox.about(self, "Warning",
                                  "Given passwords are different! Please check and try again!")
        else:
            success = False
            QMessageBox.about(self, "Warning",
                              "Please fill out all fields!")

        if success:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "Success",
                                       "Successfully registered in Storj Distributed Storage Network! "
                                       "Now, yo must verify your email by clicking link, that been send to you. "
                                       "Then you can login", QtGui.QMessageBox.Ok)
            result = msgBox.exec_()
            if result == QtGui.QMessageBox.Ok:
                self.login_window = LoginUI(self)
                self.login_window.show()
                self.close()
                initial_window.hide()

        print self.email


# Login section
class LoginUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)

        # login UI
        self.login_ui = Ui_Login()
        self.login_ui.setupUi(self)

        # Account manager

        self.login_ui.password.setEchoMode(QLineEdit.Password)

        QtCore.QObject.connect(self.login_ui.login_bt, QtCore.SIGNAL("clicked()"), self.login)  # take login action

    def login(self):
        # take login action

        self.email = self.login_ui.email.text()  # get login
        self.password = self.login_ui.password.text()  # get password

        self.storj_client = storj.Client(email=str(self.email), password=str(self.password))
        success = False
        # take login action - check credentials by listing keys :D
        try:
            self.storj_client.key_list()
            success = True
        except storj.exception.StorjBridgeApiError, e:
            j = json.loads(str(e))
            if (j["error"] == "Invalid email or password"):
                QMessageBox.about(self, "Warning",
                                  "Invalid email or password - access denied. Please check your credentials and try again!")
            else:
                QMessageBox.about(self, "Unhandled exception", "Exception: " + str(e))

        if success:
            self.account_manager = AccountManager(str(self.email), str(self.password))  # init account manager
            self.account_manager.save_account_credentials()  # save login credentials and state
            # login_msg_box = QMessageBox.about(self, "Success", "Successfully loged in!")
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "Success", "Successfully loged in!",
                                       QtGui.QMessageBox.Ok)
            result = msgBox.exec_()
            if result == QtGui.QMessageBox.Ok:
                self.main_ui_window = MainUI(self)
                self.main_ui_window.show()
                self.close()
                initial_window.hide()

                # self.account_manager.get_login_state()

        # print self.storj_client.bucket_list()
        print 1;


# StorjEngine section
class StorjEngine():
    def __init__(self):
        account_manager = AccountManager()
        if account_manager.if_logged_in():
            self.password = account_manager.get_user_password()
            self.email = account_manager.get_user_email()
            # initialize Storj
            self.storj_client = storj.Client(email=str(self.email), password=str(self.password))


# Node details section
class NodeDetailsUI(QtGui.QMainWindow):
    def __init__(self, parent=None, nodeid=None):
        QtGui.QWidget.__init__(self, parent)

        self.storj_engine = StorjEngine()  # init StorjEngine
        # login UI
        self.node_details_ui = Ui_NodeDetails()
        self.node_details_ui.setupUi(self)

        self.nodeid = nodeid
        self.tools = Tools()

        QtCore.QObject.connect(self.node_details_ui.ok_bt, QtCore.SIGNAL("clicked()"), self.close)  # close window

        self.createNewNodeDetailsResolveThread()

        ## print nodeid

    def createNewNodeDetailsResolveThread(self):
        download_thread = threading.Thread(target=self.initialize_node_details, args=())
        download_thread.start()

    def initialize_node_details(self):
        self.node_details_content = self.storj_engine.storj_client.contact_lookup(str(self.nodeid))

        self.node_details_ui.address_label.setText(
            html_format_begin + str(self.node_details_content.address) + html_format_end)  # get given node address
        self.node_details_ui.last_timeout_label.setText(
            html_format_begin + str(self.node_details_content.lastTimeout) + html_format_end)  # get last timeout
        self.node_details_ui.timeout_rate_label.setText(
            html_format_begin + str(self.node_details_content.timeoutRate) + html_format_end)  # get timeout rate
        self.node_details_ui.user_agent_label.setText(
            html_format_begin + str(self.node_details_content.userAgent) + html_format_end)  # get user agent
        self.node_details_ui.protocol_version_label.setText(
            html_format_begin + str(self.node_details_content.protocol) + html_format_end)  # get protocol version
        self.node_details_ui.response_time_label.setText(html_format_begin + str(
            self.node_details_content.responseTime) + html_format_end)  # get farmer node response time
        self.node_details_ui.port_label.setText(
            html_format_begin + str(self.node_details_content.port) + html_format_end)  # get farmer node port
        self.node_details_ui.node_id_label.setText(
            html_format_begin + str(self.nodeid) + html_format_end)  # get farmer node response time

        # ping_to_node = self.tools.measure_ping_latency(str(self.node_details_content.address))

        ip_addr = socket.gethostbyname(str(self.node_details_content.address))

        obj = IPWhois(ip_addr)
        res = obj.lookup_whois()
        country = res["nets"][0]['country']

        country_parsed = pycountry.countries.get(alpha_2=str(country))

        country_full_name = country_parsed.name

        self.node_details_ui.country_label.setText(
            html_format_begin + str(country_full_name) + html_format_end)  # set full country name

        ### Display country flag ###

        self.scene = QtGui.QGraphicsScene()

        # scene.setSceneRect(-600,-600, 600,600)
        # self.scene.setSceneRect(-600, -600, 1200, 1200)

        # pic = QtGui.QPixmap("PL.png")
        # self.scene.addItem(QtGui.QGraphicsPixmapItem(pic))
        # self.view = self.node_details_ui.country_graphicsView
        # self.view.setScene(self.scene)
        # self.view.setRenderHint(QtGui.QPainter.Antialiasing)
        # self.view.show()

        grview = self.node_details_ui.country_graphicsView()
        scene = QGraphicsScene()
        scene.addPixmap(QPixmap('PL.png'))
        grview.setScene(scene)

        grview.show()

        print country_full_name


# Mirrors section
class FileMirrorsListUI(QtGui.QMainWindow):
    def __init__(self, parent=None, bucketid=None, fileid=None):
        QtGui.QWidget.__init__(self, parent)
        self.file_mirrors_list_ui = Ui_FileMirrorsList()
        self.file_mirrors_list_ui.setupUi(self)
        # model = self.file_mirrors_list_ui.established_mirrors_tree.model()


        self.file_mirrors_list_ui.mirror_details_bt.clicked.connect(
            lambda: self.open_mirror_details_window("established"))
        self.file_mirrors_list_ui.mirror_details_bt_2.clicked.connect(
            lambda: self.open_mirror_details_window("available"))
        self.file_mirrors_list_ui.quit_bt.clicked.connect(self.close)

        # self.connect(self.file_mirrors_list_ui.established_mirrors_tree, QtCore.SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), self.open_mirror_details_window)

        # self.connect(self.file_mirrors_list_ui.established_mirrors_tree, QtCore.SIGNAL('selectionChanged()'), self.open_mirror_details_window)


        # QtCore.QObject.connect(self.file_mirrors_list_ui.established_mirrors_tree.selectionModel(), QtCore.SIGNAL('selectionChanged(QItemSelection, QItemSelection)'),
        # self.open_mirror_details_window)


        # self.file_mirrors_list_ui.established_mirrors_tree.

        self.bucketid = bucketid
        self.fileid = fileid

        self.file_mirrors_list_ui.file_id_label.setText(html_format_begin + str(self.fileid) + html_format_end)

        print self.fileid
        self.storj_engine = StorjEngine()  # init StorjEngine
        self.createNewMirrorListInitializationThread()

    def open_mirror_details_window(self, mirror_state):
        # self.established_mirrors_tree_view = self.file_mirrors_list_ui.established_mirrors_tree


        # daat = self.file_mirrors_list_ui.established_mirrors_tree.selectedIndexes()
        # model = self.file_mirrors_list_ui.established_mirrors_tree.model()
        # data = []

        # initialize variables
        item = ""
        index = ""
        try:
            if mirror_state == "established":
                index = self.file_mirrors_list_ui.established_mirrors_tree.selectedIndexes()[3]
                item = self.file_mirrors_list_ui.established_mirrors_tree.selectedIndexes()[3]
            elif mirror_state == "available":
                index = self.file_mirrors_list_ui.available_mirrors_tree.selectedIndexes()[3]
                item = self.file_mirrors_list_ui.available_mirrors_tree.selectedIndexes()[3]

            nodeid_to_send = item.model().itemFromIndex(index).text()

            if nodeid_to_send != "":
                self.node_details_window = NodeDetailsUI(self, nodeid_to_send)
                self.node_details_window.show()
            else:
                QMessageBox.about(self, "Warning", "Please select farmer node from list")
                print "Unhandled error"

        except:
            QMessageBox.about(self, "Warning", "Please select farmer node from list")
            print "Unhandled error"

    def createNewMirrorListInitializationThread(self):
        mirror_list_initialization_thread = threading.Thread(target=self.initialize_mirrors_tree, args=())
        mirror_list_initialization_thread.start()

    def initialize_mirrors_tree(self):
        # create model
        # model = QtGui.QFileSystemModel()
        # model.setRootPath(QtCore.QDir.currentPath())

        self.file_mirrors_list_ui.loading_label_mirrors_established.setStyleSheet('color: red')  # set loading color
        self.file_mirrors_list_ui.loading_label_mirrors_available.setStyleSheet('color: red')  # set loading color

        self.mirror_tree_view_header = ['Shard Hash / Address', 'User agent', 'Last seed', 'Node ID']

        ######################### set the model for established mirrors ##################################
        self.established_mirrors_model = QStandardItemModel()
        self.established_mirrors_model.setHorizontalHeaderLabels(self.mirror_tree_view_header)

        self.established_mirrors_tree_view = self.file_mirrors_list_ui.established_mirrors_tree
        self.established_mirrors_tree_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.established_mirrors_tree_view.setModel(self.established_mirrors_model)
        self.established_mirrors_tree_view.setUniformRowHeights(True)

        self.file_mirrors_list_ui.available_mirrors_tree.setModel(self.established_mirrors_model)

        divider = 0
        group = 1
        self.established_mirrors_count_for_file = 0
        recent_shard_hash = "";
        parent1 = QStandardItem('')
        for file_mirror in self.storj_engine.storj_client.file_mirrors(str(self.bucketid), str(self.fileid)):
            for mirror in file_mirror.established:
                self.established_mirrors_count_for_file += 1
                print file_mirror.established
                if mirror["shardHash"] != recent_shard_hash:
                    parent1 = QStandardItem('Shard with hash {}'.format(mirror["shardHash"]))
                    divider = divider + 1
                    self.established_mirrors_model.appendRow(parent1)

                child1 = QStandardItem(str(mirror["contact"]["address"] + ":" + str(mirror["contact"]["port"])))
                child2 = QStandardItem(str(mirror["contact"]["userAgent"]))
                child3 = QStandardItem(str(mirror["contact"]["lastSeen"]))
                child4 = QStandardItem(str(mirror["contact"]["nodeID"]))
                parent1.appendRow([child1, child2, child3, child4])

                # span container columns
                # self.established_mirrors_tree_view.setFirstColumnSpanned(1, self.established_mirrors_tree_view.rootIndex(), True)

                recent_shard_hash = mirror["shardHash"]

        self.file_mirrors_list_ui.loading_label_mirrors_established.setText("")

        # dbQueryModel.itemData(treeView.selectedIndexes()[0])

        ################################### set the model for available mirrors #########################################
        self.available_mirrors_model = QStandardItemModel()
        self.available_mirrors_model.setHorizontalHeaderLabels(self.mirror_tree_view_header)

        self.available_mirrors_tree_view = self.file_mirrors_list_ui.available_mirrors_tree
        self.available_mirrors_tree_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.available_mirrors_tree_view.setModel(self.available_mirrors_model)
        self.available_mirrors_tree_view.setUniformRowHeights(True)

        self.file_mirrors_list_ui.available_mirrors_tree.setModel(self.available_mirrors_model)

        divider = 0
        self.available_mirrors_count_for_file = 0
        recent_shard_hash_2 = "";
        parent2 = QStandardItem('')
        for file_mirror in self.storj_engine.storj_client.file_mirrors(str(self.bucketid), str(self.fileid)):
            for mirror_2 in file_mirror.available:
                self.available_mirrors_count_for_file += 1
                if mirror_2["shardHash"] != recent_shard_hash_2:
                    parent2 = QStandardItem('Shard with hash {}'.format(mirror_2["shardHash"]))
                    divider = divider + 1
                    self.available_mirrors_model.appendRow(parent2)

                child1 = QStandardItem(str(mirror_2["contact"]["address"] + ":" + str(mirror_2["contact"]["port"])))
                child2 = QStandardItem(str(mirror_2["contact"]["userAgent"]))
                child3 = QStandardItem(str(mirror_2["contact"]["lastSeen"]))
                child4 = QStandardItem(str(mirror_2["contact"]["nodeID"]))
                parent2.appendRow([child1, child2, child3, child4])

                # span container columns
                # self.established_mirrors_tree_view.setFirstColumnSpanned(1, self.established_mirrors_tree_view.rootIndex(), True)

                recent_shard_hash_2 = mirror_2["shardHash"]
        self.file_mirrors_list_ui.loading_label_mirrors_available.setText("")

        self.file_mirrors_list_ui.established_mirrors_count.setText(
            html_format_begin + str(self.established_mirrors_count_for_file) + html_format_end)
        self.file_mirrors_list_ui.available_mirrors_count.setText(
            html_format_begin + str(self.available_mirrors_count_for_file) + html_format_end)
        print QtCore.QDir.currentPath()


# Bucekts section
class BucketManagerUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.bucket_manager_ui = Ui_BucketManager()
        self.bucket_manager_ui.setupUi(self)
        self.createNewBucketGetThread()

        QtCore.QObject.connect(self.bucket_manager_ui.quit_bt, QtCore.SIGNAL("clicked()"),
                               self.quit)  # open login window
        QtCore.QObject.connect(self.bucket_manager_ui.delete_bucket_bt, QtCore.SIGNAL("clicked()"),
                               self.delete_bucket)  # delete bucket
        QtCore.QObject.connect(self.bucket_manager_ui.edit_bucket_bt, QtCore.SIGNAL("clicked()"),
                               self.open_bucket_edit_window)  # open bucket edit window
        # QtCore.QObject.connect(self.ui.pushButton_4, QtCore.SIGNAL("clicked()"), self.open_register_window) # open login window

    def createNewBucketGetThread(self):
        download_thread = threading.Thread(target=self.initialize_buckets_table, args=())
        download_thread.start()

    def quit(self):
        self.close()

    def delete_bucket(self):
        # initialize variables
        bucket_id = ""
        bucket_name = ""

        tablemodel = self.bucket_manager_ui.bucket_list_tableview.model()
        rows = sorted(set(index.row() for index in self.bucket_manager_ui.bucket_list_tableview.selectedIndexes()))
        i = 0
        for row in rows:
            index = tablemodel.index(row, 3)  # get bucket ID
            index2 = tablemodel.index(row, 2)  # get bucket name
            # We suppose data are strings
            bucket_id = str(tablemodel.data(index).toString())
            bucket_name = str(tablemodel.data(index2).toString())
            i = i + 1
            break

        if i != 0:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Question, "Are you sure?",
                                       "Are you sure to delete this bucket? Bucket name: '" + bucket_name + "'",
                                       QtGui.QMessageBox.Ok)
            result = msgBox.exec_()
            if result == QtGui.QMessageBox.Ok:
                success = False
                try:
                    self.storj_engine.storj_client.bucket_delete(str(bucket_id))
                    success = True
                except storj.exception.StorjBridgeApiError, e:
                    QMessageBox.about(self, "Unhandled exception deleting bucket", "Exception: " + str(e))
                    success = False

                if success:
                    QMessageBox.about(self, "Success", "Bucket was deleted successfully!")
        else:
            QMessageBox.about(self, "Warning", "Please select bucket which you want to delete.")

    def open_bucket_edit_window(self):
        print 1

    def initialize_buckets_table(self):
        self.storj_engine = StorjEngine()  # init StorjEngine
        model = QStandardItemModel(1, 1)  # initialize model for inserting to table

        model.setHorizontalHeaderLabels(['Name', 'Storage', 'Transfer', 'ID'])

        i = 0
        try:
            for bucket in self.storj_engine.storj_client.bucket_list():
                item = QStandardItem(bucket.name)
                model.setItem(i, 0, item)  # row, column, item (QStandardItem)

                item = QStandardItem(str(bucket.storage))
                model.setItem(i, 1, item)  # row, column, item (QStandardItem)

                item = QStandardItem(str(bucket.transfer))
                model.setItem(i, 2, item)  # row, column, item (QStandardItem)

                item = QStandardItem(bucket.id)
                model.setItem(i, 3, item)  # row, column, item (QStandardItem)

                i = i + 1
        except storj.exception.StorjBridgeApiError, e:
            QMessageBox.about(self, "Unhandled bucket resolving exception", "Exception: " + str(e))

        self.bucket_manager_ui.total_buckets_label.setText(str(i))  # set label of user buckets number
        self.bucket_manager_ui.bucket_list_tableview.setModel(model)
        self.bucket_manager_ui.bucket_list_tableview.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)


######################################################################################################################################
####################### BUCKET CREATE UI ##################################

class BucketCreateUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.bucket_create_ui = Ui_BucketCreate()
        self.bucket_create_ui.setupUi(self)

        QtCore.QObject.connect(self.bucket_create_ui.create_bucket_bt, QtCore.SIGNAL("clicked()"),
                               self.createNewBucketCreateThread)  # create bucket action
        QtCore.QObject.connect(self.bucket_create_ui.cancel_bt, QtCore.SIGNAL("clicked()"),
                               self.close)  # create bucket action

        self.storj_engine = StorjEngine()  # init StorjEngine

    def createNewBucketCreateThread(self):
        bucket_create_thread = threading.Thread(target=self.create_bucket, args=())
        bucket_create_thread.start()

    def create_bucket(self):
        self.bucket_name = self.bucket_create_ui.bucket_name.text()
        self.bucket_storage = self.bucket_create_ui.bucket_storage_size.text()
        self.bucket_transfer = self.bucket_create_ui.bucket_transfer.text()

        bucekt_cerated = False  # init boolean
        if self.bucket_name != "" and self.bucket_transfer != "" and self.bucket_storage != "":

            try:
                self.storj_engine.storj_client.bucket_create(str(self.bucket_name), int(self.bucket_storage),
                                                             int(self.bucket_transfer))
                bucekt_cerated = True
            except  storj.exception.StorjBridgeApiError, e:
                bucekt_cerated = False
                QMessageBox.about(self, "Unhandled exception while creating bucket", "Exception: " + str(e))

        else:
            QMessageBox.about(self, "Warning", "Please fill out all fields!")
            bucekt_cerated = False

        if bucekt_cerated:
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Information, "Success", "Bucket was created successfully!",
                                       QtGui.QMessageBox.Ok)
            msgBox.exec_()
            # QMessageBox.about(self, "Success", "Bucket was created successfully!", QMessageBox.Ok)

        print 1


######################################################################################################################################
####################### FILE MANAGER UI ##################################

# Files section
class FileManagerUI(QtGui.QMainWindow):
    def __init__(self, parent=None, bucketid=None):
        QtGui.QWidget.__init__(self, parent)
        self.file_manager_ui = Ui_FileManager()
        self.file_manager_ui.setupUi(self)

        QtCore.QObject.connect(self.file_manager_ui.bucket_select_combo_box,
                               QtCore.SIGNAL("currentIndexChanged(const QString&)"),
                               self.createNewFileListUpdateThread)  # connect ComboBox change listener
        QtCore.QObject.connect(self.file_manager_ui.file_mirrors_bt, QtCore.SIGNAL("clicked()"),
                               self.open_mirrors_list_window)  # create bucket action
        QtCore.QObject.connect(self.file_manager_ui.quit_bt, QtCore.SIGNAL("clicked()"),
                               self.close)  # create bucket action
        QtCore.QObject.connect(self.file_manager_ui.file_download_bt, QtCore.SIGNAL("clicked()"),
                               self.open_single_file_download_window)  # create bucket action
        QtCore.QObject.connect(self.file_manager_ui.file_delete_bt, QtCore.SIGNAL("clicked()"),
                               self.delete_selected_file)  # delete selected file

        self.storj_engine = StorjEngine()  # init StorjEngine
        self.createNewBucketResolveThread()

    def delete_selected_file(self):


        self.current_bucket_index = self.file_manager_ui.bucket_select_combo_box.currentIndex()
        self.current_selected_bucket_id = self.bucket_id_list[self.current_bucket_index]

        tablemodel = self.file_manager_ui.files_list_tableview.model()
        rows = sorted(set(index.row() for index in
                          self.file_manager_ui.files_list_tableview.selectedIndexes()))

        selected = False
        for row in rows:
            selected = True
            index = tablemodel.index(row, 3)  # get file ID index
            index_filename = tablemodel.index(row, 0)  # get file name index

            # We suppose data are strings
            selected_file_id = str(tablemodel.data(index).toString())
            selected_file_name = str(tablemodel.data(index_filename).toString())
            msgBox = QtGui.QMessageBox(QtGui.QMessageBox.Question, "Question",
                                       "Are you sure you want to delete this file? File name: " + selected_file_name, QtGui.QMessageBox.Yes)
            result = msgBox.exec_()
            print result
            if result != QtGui.QMessageBox.Rejected:
                try:
                    self.storj_engine.storj_client.file_remove(str(self.current_selected_bucket_id), str(selected_file_id))
                    self.createNewFileListUpdateThread() # update files list
                    QMessageBox.about(self, "Success", 'File "' + str(selected_file_name) + '" was deleted successfully')
                except storj.exception.StorjBridgeApiError, e:
                    QMessageBox.about(self, "Error", "Bridge exception occured while trying to delete file: " + str(e))
                except Exception, e:
                    QMessageBox.about(self, "Error", "Unhandled exception occured while trying to delete file: " + str(e))

        if not selected:
            QMessageBox.about(self, "Information", "Please select file which you want to delete")

        return True

    def open_mirrors_list_window(self):
        self.current_bucket_index = self.file_manager_ui.bucket_select_combo_box.currentIndex()
        self.current_selected_bucket_id = self.bucket_id_list[self.current_bucket_index]

        tablemodel = self.file_manager_ui.files_list_tableview.model()
        rows = sorted(set(index.row() for index in
                          self.file_manager_ui.files_list_tableview.selectedIndexes()))
        i = 0
        for row in rows:
            print('Row %d is selected' % row)
            index = tablemodel.index(row, 3)  # get file ID
            # We suppose data are strings
            selected_file_id = str(tablemodel.data(index).toString())
            self.file_mirrors_list_window = FileMirrorsListUI(self, str(self.current_selected_bucket_id),
                                                              selected_file_id)
            self.file_mirrors_list_window.show()
            i += 1

        if i == 0:
            QMessageBox.about(self, "Warning!", "Please select file from file list!")

        print 1

    def createNewFileListUpdateThread(self):
        download_thread = threading.Thread(target=self.update_files_list, args=())
        download_thread.start()

    def update_files_list(self):

        self.tools = Tools()

        model = QStandardItemModel(1, 1)  # initialize model for inserting to table

        model.setHorizontalHeaderLabels(['File name', 'File size', 'Mimetype', 'File ID'])

        self.current_bucket_index = self.file_manager_ui.bucket_select_combo_box.currentIndex()
        self.current_selected_bucket_id = self.bucket_id_list[self.current_bucket_index]

        i = 0

        for self.file_details in self.storj_engine.storj_client.bucket_files(str(self.current_selected_bucket_id)):
            item = QStandardItem(str(self.file_details["filename"]))
            model.setItem(i, 0, item)  # row, column, item (QStandardItem)

            file_size_str = self.tools.human_size(int(self.file_details["size"])) # get human readable file size

            item = QStandardItem(str(file_size_str))
            model.setItem(i, 1, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str(self.file_details["mimetype"]))
            model.setItem(i, 2, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str(self.file_details["id"]))
            model.setItem(i, 3, item)  # row, column, item (QStandardItem)

            i = i + 1

            print self.file_details

        self.file_manager_ui.files_list_tableview.clearFocus()
        self.file_manager_ui.files_list_tableview.setModel(model)
        self.file_manager_ui.files_list_tableview.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

    def createNewBucketResolveThread(self):
        download_thread = threading.Thread(target=self.initialize_bucket_select_combobox, args=())
        download_thread.start()

    def initialize_bucket_select_combobox(self):
        self.buckets_list = []
        self.bucket_id_list = []
        self.storj_engine = StorjEngine()  # init StorjEngine
        i = 0
        try:
            for bucket in self.storj_engine.storj_client.bucket_list():
                self.buckets_list.append(str(bucket.name))  # append buckets to list
                self.bucket_id_list.append(str(bucket.id))  # append buckets to list
                i = i + 1
        except storj.exception.StorjBridgeApiError, e:
            QMessageBox.about(self, "Unhandled bucket resolving exception", "Exception: " + str(e))

        self.file_manager_ui.bucket_select_combo_box.addItems(self.buckets_list)

    def open_single_file_download_window(self):
        self.single_file_download_window = SingleFileDownloadUI(self)
        self.single_file_download_window.show()


# Initial window section

class InitialWindowUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui_initial_window = Ui_InitialWindow()
        self.ui_initial_window.setupUi(self)
        # QtCore.QObject.connect(self.ui.pushButton_3, QtCore.SIGNAL("clicked()"), self.save_config) # open bucket manager
        self.storj_engine = StorjEngine()  # init StorjEngine

        QtCore.QObject.connect(self.ui_initial_window.login_bt, QtCore.SIGNAL("clicked()"),
                               self.open_login_window)  # open login window
        QtCore.QObject.connect(self.ui_initial_window.register_bt, QtCore.SIGNAL("clicked()"),
                               self.open_register_window)  # open login window
        # QtCore.QObject.connect(self.ui_initial_window.about_bt, QtCore.SIGNAL("clicked()"), self.open_about_window) # open login window


        # self.storj_engine.storj_client.

    def open_login_window(self):
        self.login_window = LoginUI(self)
        self.login_window.show()

    def open_register_window(self):
        self.register_window = RegisterUI(self)
        self.register_window.show()


# Main UI section
class MainUI(QtGui.QMainWindow):
    def __init__(self, parent=None):
        EXIT_CODE_REBOOT = -123
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_MainMenu()
        self.ui.setupUi(self)
        # QtCore.QObject.connect(self.ui.pushButton_3, QtCore.SIGNAL("clicked()"), self.save_config) # open bucket manager
        self.storj_engine = StorjEngine()  # init StorjEngine
        # self.storj_engine.storj_client.
        self.sharding_tools = ShardingTools()

        print self.sharding_tools.get_optimal_shard_parametrs(18888888888)
        # print self.sharding_tools.determine_shard_size(12343446576, 10)
        self.account_manager = AccountManager()  # init AccountManager

        user_email = self.account_manager.get_user_email()
        self.ui.account_label.setText(html_format_begin + str(user_email) + html_format_end)

        # QtCore.QObject.connect(self.ui., QtCore.SIGNAL("clicked()"), self.open_login_window) # open login window
        # QtCore.QObject.connect(self.ui.pushButton_4, QtCore.SIGNAL("clicked()"), self.open_register_window) # open login window
        QtCore.QObject.connect(self.ui.bucket_menager_bt, QtCore.SIGNAL("clicked()"),
                               self.open_bucket_manager_window)  # open bucket manager window
        QtCore.QObject.connect(self.ui.file_manager_bt, QtCore.SIGNAL("clicked()"),
                               self.open_file_manager_window)  # open file manager window
        QtCore.QObject.connect(self.ui.create_bucket_bt, QtCore.SIGNAL("clicked()"),
                               self.open_bucket_create_window)  # open bucket create window
        QtCore.QObject.connect(self.ui.uploader_bt, QtCore.SIGNAL("clicked()"),
                               self.open_single_file_upload_window)  # open single file upload ui
        QtCore.QObject.connect(self.ui.settings_bt, QtCore.SIGNAL("clicked()"),
                               self.open_settings_window)  # open single file upload ui
        # QtCore.QObject.connect(self.ui.pushButton_7, QtCore.SIGNAL("clicked()"), self.open_file_mirrors_list_window) # open file mirrors list window

    def open_login_window(self):
        self.login_window = LoginUI(self)
        self.login_window.show()

        self.login_window = ClientConfigurationUI(self)
        self.login_window.show()

        # take login action
        print 1;

    def open_register_window(self):
        self.register_window = RegisterUI(self)
        self.register_window.show()

    def open_single_file_upload_window(self):
        self.single_file_upload_window = SingleFileUploadUI(self)
        self.single_file_upload_window.show()

    def open_bucket_manager_window(self):
        self.bucket_manager_window = BucketManagerUI(self)
        self.bucket_manager_window.show()

    def open_file_manager_window(self):
        self.file_manager_window = FileManagerUI(self)
        self.file_manager_window.show()

    def open_bucket_create_window(self):
        self.bucket_create_window = BucketCreateUI(self)
        self.bucket_create_window.show()

    def open_file_mirrors_list_window(self):
        self.file_mirrors_list_window = FileMirrorsListUI(self)
        self.file_mirrors_list_window.show()

    def open_settings_window(self):
        self.settings_window = ClientConfigurationUI(self)
        self.settings_window.show()


class SingleFileDownloadUI(QtGui.QMainWindow):
    def __init__(self, parent=None, bucketid=None, fileid=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui_single_file_download = Ui_SingleFileDownload()
        self.ui_single_file_download.setupUi(self)
        # QtCore.QObject.connect(self.ui_single_file_download., QtCore.SIGNAL("clicked()"), self.save_config) # open bucket manager
        self.storj_engine = StorjEngine()  # init StorjEngine



        #self.initialize_shard_queue_table(file_pointers)

        QtCore.QObject.connect(self.ui_single_file_download.file_save_path_bt, QtCore.SIGNAL("clicked()"),
                               self.select_file_save_path)  # open file select dialog
        QtCore.QObject.connect(self.ui_single_file_download.tmp_dir_bt, QtCore.SIGNAL("clicked()"),
                               self.select_tmp_directory)  # open tmp directory select dialog
        QtCore.QObject.connect(self.ui_single_file_download.start_download_bt, QtCore.SIGNAL("clicked()"),
                               self.initialize_shard_queue_table)  # begin file downloading process

        file_metadata = self.storj_engine.storj_client.file_metadata("dc4778cc186192af49475b49", "07a2a9ebff6b7785b4bb18fd")

        self.ui_single_file_download.file_name.setText(html_format_begin + str(file_metadata.filename) + html_format_end)

    def set_current_status(self, current_status):
        self.ui_single_file_download.current_state.setText(html_format_begin + current_status + html_format_end)

    def select_tmp_directory(self):
        self.selected_tmp_dir = QtGui.QFileDialog.getExistingDirectory(None, 'Select a folder:', '',
                                                                       QtGui.QFileDialog.ShowDirsOnly)
        self.ui_single_file_download.tmp_dir.setText(str(self.selected_tmp_dir))

    def select_file_save_path(self):
        self.ui_single_file_download.file_save_path.setText(QFileDialog.getOpenFileName())

    def initialize_shard_queue_table(self, file_pointers=None):


        file_pointers = self.storj_engine.storj_client.file_pointers("dc4778cc186192af49475b49", "1c2d637b06e2ea56e70b6c6b")
        options_array = {}

        i = 0
        model = QStandardItemModel(1, 1)  # initialize model for inserting to table

        model.setHorizontalHeaderLabels(['Progress', 'Hash', 'Farmer addres', 'State', 'Shard index'])
        for pointer in file_pointers:
            item = QStandardItem(str(""))
            model.setItem(i, 0, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str(pointer["hash"]))
            model.setItem(i, 1, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str(pointer["farmer"]["address"] + ":" + str(pointer["farmer"]["port"])))
            model.setItem(i, 2, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str("Waiting..."))
            model.setItem(i, 3, item)  # row, column, item (QStandardItem)

            item = QStandardItem(str(pointer["index"]))
            model.setItem(i, 4, item)  # row, column, item (QStandardItem)

            options_array["file_size_shard_" + str(i)] = pointer["size"]
            i = i + 1
            #print  str(pointer["index"])+"index"

        self.ui_single_file_download.shard_queue_table.clearFocus()
        self.ui_single_file_download.shard_queue_table.setModel(model)
        self.ui_single_file_download.shard_queue_table.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

        i2 = 0
        progressbar_list = []
        for pointer in file_pointers:
            tablemodel = self.ui_single_file_download.shard_queue_table.model()
            index = tablemodel.index(i2, 0)
            progressbar_list.append(QProgressBar())
            self.ui_single_file_download.shard_queue_table.setIndexWidget(index, progressbar_list[i2])
            i2 = i2 + 1

        options_array["file_pointers"] = file_pointers
        options_array["file_pointers_is_given"] = "1"
        options_array["progressbars_enabled"] = "1"
        options_array["file_size_is_given"] = "1"
        options_array["shards_count"] = i

        self.ui_single_file_download.total_shards.setText(html_format_begin + str(i) + html_format_end)

        #storj_sdk_overrides = StorjSDKImplementationsOverrides()

        self.file_download(None, None, "/home/lakewik/rudasek1", options_array, progressbar_list)
        # progressbar_list[0].setValue(20)
        # progressbar_list[2].setValue(17)

    def calculate_final_hmac(self):
        return 1

    def create_download_connection(self, url, path_to_save, options_chain, progress_bar):
        local_filename = path_to_save
        downloaded = False

        while True:
            try:
                if options_chain["handle_progressbars"] != "1":
                    r = requests.get(url)
                    # requests.
                    with open(local_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)
                else:
                    r = requests.get(url, stream=True)
                    f = open(local_filename, 'wb')
                    if options_chain["file_size_is_given"] == "1":
                        file_size = options_chain["shard_file_size"]
                    else:
                        file_size = int(r.headers['Content-Length'])

                    chunk = 1
                    num_bars = file_size / chunk
                    t1 = float(file_size) / float((32 * 1024))
                    print t1

                    if file_size <= (32 * 1024):
                        t1 = 1

                    i = 0
                    print file_size
                    print str(t1) + "kotek"
                    for chunk in r.iter_content(32 * 1024):
                        i += 1
                        f.write(chunk)
                        print str(i) + " " + str(t1)
                        print round(float(i) / float(t1), 1)
                        print str(int(round((100.0 * i) / t1))) + " %"
                        if int(round((100.0 * i) / t1)) > 100:
                            percent_downloaded = 100
                        else:
                            percent_downloaded = int(round((100.0 * i) / t1))
                        progress_bar.setValue(percent_downloaded)

                    f.close()
                    downloaded = True
            except Exception:
                continue
            else:
                downloaded = True
                break

        if not downloaded:
            self.emit(SIGNAL("retryWithNewDownloadPointer"), options_chain["shard_index"])  # retry download with new download pointer
        else:
            self.emit(SIGNAL("incrementShardsDownloadProgressCounters"))  # update already uploaded shards count
            self.emit(SIGNAL("updateDownloadTaskState"), options_chain["rowposition"], "Downloaded!")  # update shard upload state


            return

    def createNewDownloadThread(self, url, filelocation, options_chain, progress_bars_list):
        # self.download_thread = DownloadTaskQtThread(url, filelocation, options_chain, progress_bars_list)
        # self.download_thread.start()
        # self.download_thread.connect(self.download_thread, SIGNAL('setStatus'), self.test1, Qt.QueuedConnection)
        # self.download_thread.tick.connect(progress_bars_list.setValue)

        # Refactor to QtTrhead
        download_thread = threading.Thread(target=self.create_download_connection,
                                           args=(url, filelocation, options_chain, progress_bars_list))
        download_thread.start()

    def test1(self, value1, value2):
        print str(value1) + " aaa " + str(value2)

    def upload_file(self):
        print 1;

    def file_download(self, bucket_id, file_id, file_save_path, options_array, progress_bars_list):
        options_chain = {}
        self.storj_engine.storj_client.logger.info('file_pointers(%s, %s)', bucket_id, file_id)

        # Determine file pointers
        if options_array["file_pointers_is_given"] == "1":
            pointers = options_array["file_pointers"]
        else:
            pointers = self.storj_engine.storj_client.file_pointers(bucket_id=bucket_id, file_id=file_id)

        if options_array["progressbars_enabled"] == "1":
            options_chain["handle_progressbars"] = "1"

        if options_array["file_size_is_given"] == "1":
            options_chain["file_size_is_given"] = "1"

        shards_count = int(options_array["shards_count"])

        i = 0
        shard_size_array = []
        while i < shards_count:
            shard_size_array.append(int(options_array["file_size_shard_" + str(i)]))
            i += 1
        print shard_size_array
        part = 0
        self.set_current_status("Starting download threads...")
        for pointer in pointers:
            self.set_current_status("Downloading shard at index " + str(part) + "...")

            print pointer
            options_chain["shard_file_size"] = shard_size_array[part]
            url = "http://" + pointer.get('farmer')['address'] + ":" + str(pointer.get('farmer')['port']) + "/shards/" + \
                  pointer["hash"] + "?token=" + pointer["token"]
            print url
            self.createNewDownloadThread(url, file_save_path + "part" + str(part), options_chain, progress_bars_list[part])
            part = part + 1


        fileisencrypted = True

        if fileisencrypted:
            # decrypt file
            self.set_current_status("Decrypting file...")
            #self.set_current_status()
            file_crypto_tools = FileCrypto()
            #file_crypto_tools.decrypt_file("AES", str(file_path), self.parametrs.tmpPath + bname , "kotecze57") # begin file encryption

        print "pobrano"

        return True


class DownloadTaskQtThread(QtCore.QThread):
    tick = QtCore.pyqtSignal(int, name="upload_changed")

    def __init__(self, url, path_to_save, options_chain, progress_bar):
        QtCore.QThread.__init__(self)
        self.obj_thread = QtCore.QThread()
        self.url = url
        self.path_to_save = path_to_save
        self.options_chain = options_chain
        self.progress_bar = progress_bar

        # def run(self):
        # self.client.create_download_connection(self, None, None, None, None)

    # def create_download_connection(self, url, path_to_save, options_chain, progress_bar):
    def run(self):
        print "test"
        local_filename = self.path_to_save
        if self.options_chain["handle_progressbars"] != "1":
            r = requests.get(self.url)
            # requests.
            with open(self.local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
        else:
            r = requests.get(self.url, stream=True)
            f = open(local_filename, 'wb')
            if self.options_chain["file_size_is_given"] == "1":
                file_size = self.options_chain["shard_file_size"]
            else:
                file_size = int(r.headers['Content-Length'])

            chunk = 1
            num_bars = file_size / chunk
            t1 = file_size / (32 * 1024)
            i = 0
            print file_size
            for chunk in r.iter_content(32 * 1024):
                f.write(chunk)
                print str(i) + " " + str(t1)
                print round(float(i) / float(t1), 1)
                print str(int(round((100.0 * i) / t1))) + " %"
                percent_downloaded = int(round((100.0 * i) / t1))
                # Refactor for fix SIGSEGV
                # self.tick.emit(percent_downloaded)
                # self.emit(SIGNAL("setStatus"), percent_downloaded , "information")
                # Old
                # progress_bar.setValue (percent_downloaded)
                i += 1
            f.close()
            return


##################### CRYPTOGRAPHY TOOLS ################################
class CryptoTools():
    def calculate_hmac(self, base_string, key):
        """
        HMAC hash calculation and returning the results in dictionary collection
        FROM: <https://janusznawrat.wordpress.com/2015/04/08/wyliczanie-kryptograficznych-sum-kontrolnych-hmac-plikow-i-lancuchow-znakowych/>
        """
        hmacs = dict()
        # --- MD5 ---
        hashed = hmac.new(key, base_string, hashlib.md5)
        hmac_md5 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['MD5'] = hmac_md5
        # --- SHA-1 ---
        hashed = hmac.new(key, base_string, hashlib.sha1)
        hmac_sha1 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-1'] = hmac_sha1
        # --- SHA-224 ---
        hashed = hmac.new(key, base_string, hashlib.sha224)
        hmac_sha224 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-224'] = hmac_sha224
        # --- SHA-256 ---
        hashed = hmac.new(key, base_string, hashlib.sha256)
        hmac_sha256 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-256'] = hmac_sha256
        # --- SHA-384 ---
        hashed = hmac.new(key, base_string, hashlib.sha384)
        hmac_sha384 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-384'] = hmac_sha384
        # --- SHA-512 ---
        hashed = hmac.new(key, base_string, hashlib.sha512)
        hmac_sha512 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-512'] = hmac_sha512
        return hmacs

    def prepare_bucket_entry_hmac(self, shard_array):
        storj_keyring = storj.model.Keyring()
        encryption_key = storj_keyring.get_encryption_key("test")
        current_hmac = ""
        for shard in shard_array:
            base64_decoded = str(base64.decodestring(shard.hash)) + str(current_hmac)
            current_hmac = self.calculate_hmac(base64_decoded, encryption_key)

        print current_hmac
        return current_hmac


class StorjSDKImplementationsOverrides():
    def __init__(self, parent=None):
        self.storj_engine = StorjEngine()  # init StorjEngine




################################################################# SINGLE FILE UPLOADER UI SECTION ###################################################################
class SingleFileUploadUI(QtGui.QMainWindow):
    def __init__(self, parent=None, bucketid=None, fileid=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui_single_file_upload = Ui_SingleFileUpload()
        self.ui_single_file_upload.setupUi(self)
        QtCore.QObject.connect(self.ui_single_file_upload.start_upload_bt, QtCore.SIGNAL("clicked()"),
                               self.createNewUploadThread)  # open bucket manager
        QtCore.QObject.connect(self.ui_single_file_upload.file_path_select_bt, QtCore.SIGNAL("clicked()"),
                               self.select_file_path)  # open file select dialog
        QtCore.QObject.connect(self.ui_single_file_upload.tmp_path_select_bt, QtCore.SIGNAL("clicked()"),
                               self.select_tmp_directory)  # open tmp directory select dialog
        self.storj_engine = StorjEngine()  # init StorjEngine

        self.initialize_upload_queue_table()



        # initialize variables
        self.shards_already_uploaded = 0
        self.uploaded_shards_count = 0
        self.upload_queue_progressbar_list = []

        self.connect(self, SIGNAL("addRowToUploadQueueTable"), self.add_row_upload_queue_table)

        self.connect(self, SIGNAL("incrementShardsProgressCounters"), self.increment_shards_progress_counters)
        self.connect(self, SIGNAL("updateUploadTaskState"), self.update_upload_task_state)
        self.connect(self, SIGNAL("updateShardUploadProgress"), self.update_shard_upload_progess)


        # file_pointers = self.storj_engine.storj_client.file_pointers("6acfcdc62499144929cf9b4a", "dfba26ab34466b1211c60d02")

        #self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")
        #self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")
        #self.emit(SIGNAL("incrementShardsProgressCounters"))


        # self.initialize_shard_queue_table(file_pointers)
    def update_shard_upload_progess (self, row_position_index, value):
        self.upload_queue_progressbar_list[row_position_index].setValue(value)
        print "kotek"
        return 1

    def update_upload_task_state(self, row_position, state):
        self.ui_single_file_upload.shard_queue_table_widget.setItem(int(row_position), 3, QtGui.QTableWidgetItem(str(state)))


    def increment_shards_progress_counters(self):
        self.shards_already_uploaded += 1
        self.ui_single_file_upload.shards_uploaded.setText(html_format_begin + str(self.shards_already_uploaded) + html_format_end)

    def add_row_upload_queue_table(self, row_data):
        self.upload_queue_progressbar_list.append(QProgressBar())

        self.upload_queue_table_row_count = self.ui_single_file_upload.shard_queue_table_widget.rowCount()

        self.ui_single_file_upload.shard_queue_table_widget.setRowCount(self.upload_queue_table_row_count+1)

        self.ui_single_file_upload.shard_queue_table_widget.setCellWidget(self.upload_queue_table_row_count, 0, self.upload_queue_progressbar_list[self.upload_queue_table_row_count])
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 1, QtGui.QTableWidgetItem(row_data["hash"]))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 2, QtGui.QTableWidgetItem(str(row_data["farmer_address"]) + ":" + str(row_data["farmer_port"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 3, QtGui.QTableWidgetItem(str(row_data["state"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 4, QtGui.QTableWidgetItem(str(row_data["token"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 5, QtGui.QTableWidgetItem(str(row_data["shard_index"])))

        self.upload_queue_progressbar_list[self.upload_queue_table_row_count].setValue(0)

        print row_data

    def select_tmp_directory(self):
        self.selected_tmp_dir = QtGui.QFileDialog.getExistingDirectory(None, 'Select a folder:', '',
                                                                       QtGui.QFileDialog.ShowDirsOnly)
        self.ui_single_file_upload.tmp_path.setText(str(self.selected_tmp_dir))

    def select_file_path(self):
        self.ui_single_file_upload.file_path.setText(QFileDialog.getOpenFileName())

    def createNewUploadThread(self):
        # self.download_thread = DownloadTaskQtThread(url, filelocation, options_chain, progress_bars_list)
        # self.download_thread.start()
        # self.download_thread.connect(self.download_thread, SIGNAL('setStatus'), self.test1, Qt.QueuedConnection)
        # self.download_thread.tick.connect(progress_bars_list.setValue)

        # Refactor to QtTrhead
        upload_thread = threading.Thread(target=self.file_upload_begin, args=())
        upload_thread.start()

    def initialize_upload_queue_table(self):

        # initialize variables
        self.shards_already_uploaded = 0
        self.uploaded_shards_count = 0
        self.upload_queue_progressbar_list = []

        self.upload_queue_table_header = ['Progress', 'Hash', 'Farmer', 'State', 'Token', 'Shard index']
        self.ui_single_file_upload.shard_queue_table_widget.setColumnCount(6)
        self.ui_single_file_upload.shard_queue_table_widget.setRowCount(0)
        horHeaders = self.upload_queue_table_header
        self.ui_single_file_upload.shard_queue_table_widget.setHorizontalHeaderLabels(horHeaders)
        self.ui_single_file_upload.shard_queue_table_widget.resizeColumnsToContents()
        self.ui_single_file_upload.shard_queue_table_widget.resizeRowsToContents()


        self.ui_single_file_upload.shard_queue_table_widget.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

    def set_current_status(self, current_status):
        self.ui_single_file_upload.current_state.setText(html_format_begin + current_status + html_format_end)

    def createNewShardUploadThread(self, shard, chapters, frame, file_name):
        # another worker thread for single shard uploading and it will retry if download fail
        upload_thread = threading.Thread(target=self.upload_shard(shard=shard, chapters=chapters, frame=frame, file_name_ready_to_shard_upload=file_name), args=())
        upload_thread.start()

    def upload_shard(self, shard, chapters, frame, file_name_ready_to_shard_upload):

        self.uploadblocksize = 4096

        def read_in_chunks(file_object, shard_size, rowposition, blocksize=self.uploadblocksize, chunks=-1):
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k."""

            i = 0
            while chunks:
                data = file_object.read(blocksize)
                if not data:
                    break
                yield data
                i += 1
                t1 = float(shard_size) / float((self.uploadblocksize))
                if t1 <= (self.uploadblocksize):
                    t1 = 1

                percent_uploaded = int(round((100.0 * i) / t1))

                print i
                chunks -= 1
                self.emit(SIGNAL("updateShardUploadProgress"), 0,
                          percent_uploaded)  # update progress bar in upload queue table

        it = 0
        while True:

            # emit signal to add row to upload queue table
            # self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")


            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Adding shard " + str(
                    chapters) + " to file frame and getting contract..." + html_format_end)

            try:
                frame_content = self.storj_engine.storj_client.frame_add_shard(shard, frame.id)

                # Add items to shard queue table view

                tablerowdata = {}
                tablerowdata["farmer_address"] = frame_content["farmer"]["address"]
                tablerowdata["farmer_port"] = frame_content["farmer"]["port"]
                tablerowdata["hash"] = str(shard.hash)
                tablerowdata["state"] = "Uploading..."
                tablerowdata["token"] = frame_content["token"]
                tablerowdata["shard_index"] = str(chapters)

                self.emit(SIGNAL("addRowToUploadQueueTable"), tablerowdata)  # add row to table

                rowcount = self.ui_single_file_upload.shard_queue_table_widget.rowCount()

                print frame_content
                print shard
                # frame_content.
                print frame_content["farmer"]["address"]

                farmerNodeID = frame_content["farmer"]["nodeID"]

                url = "http://" + frame_content["farmer"]["address"] + ":" + str(
                    frame_content["farmer"]["port"]) + "/shards/" + frame_content["hash"] + "?token=" + \
                      frame_content["token"]
                print url

                # files = {'file': open(file_path + '.part%s' % chapters)}
                # headers = {'content-type: application/octet-stream', 'x-storj-node-id: ' + str(farmerNodeID)}

                self.set_current_status("Uploading shard" + str(chapters + 1) + "to farmer...")

                # begin recording exchange report
                exchange_report = storj.model.ExchangeReport()

                current_timestamp = int(time.time())

                exchange_report.exchangeStart = str(current_timestamp)
                exchange_report.farmerId = str(farmerNodeID)
                exchange_report.dataHash = str(shard.hash)

                shard_size = int(shard.size)

                rowposition = it

                while True:
                    try:
                        with open(self.parametrs.tmpPath + file_name_ready_to_shard_upload + '-' + str(chapters + 1),
                                  'rb') as f:
                            response = requests.post(url, data=read_in_chunks(f, shard_size, rowposition), timeout=1)

                        j = json.loads(str(response.content))
                        if (j["result"] == "The supplied token is not accepted"):
                            raise storj.exception.StorjFarmerError(
                                storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED)

                    except Exception, e:
                        self.emit(SIGNAL("updateUploadTaskState"), rowposition,
                                  "First try failed. Retrying...")  # update shard upload state
                        print str(e)
                        continue
                    else:
                        self.emit(SIGNAL("incrementShardsProgressCounters"))  # update already uploaded shards count
                        self.emit(SIGNAL("updateUploadTaskState"), rowposition,
                                  "Uploaded!")  # update shard upload state
                        break

                print response.content

                j = json.loads(str(response.content))
                if (j["result"] == "The supplied token is not accepted"):
                    raise storj.exception.StorjFarmerError(storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED)


                firstiteration = False
                it += 1

            except storj.exception.StorjBridgeApiError, e:
                # upload failed due to Storj Bridge failure
                print "Exception raised while trying to negitiate contract: " + str(e)
                continue
            except storj.exception.StorjFarmerError, e:
                # upload failed due to Farmer Failure
                print str(e)
                if str(e) == str(storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED):
                    print "The supplied token not accepted"
                #print "Exception raised while trying to negitiate contract: " + str(e)
                continue
            except Exception, e:
                # now send Exchange Report
                # upload failed probably while sending data to farmer
                print "Error occured while trying to upload shard or negotiate contract. Retrying... " + str(e)
                current_timestamp = int(time.time())

                exchange_report.exchangeEnd = str(current_timestamp)
                exchange_report.exchangeResultCode = (exchange_report.FAILURE)
                exchange_report.exchangeResultMessage = (exchange_report.STORJ_REPORT_UPLOAD_ERROR)
                self.set_current_status("Sending Exchange Report for shard " + str(chapters + 1))
                # self.storj_engine.storj_client.send_exchange_report(exchange_report) # send exchange report
                continue
            else:
                # uploaded with success
                current_timestamp = int(time.time())
                # prepare second half of exchange heport
                exchange_report.exchangeEnd = str(current_timestamp)
                exchange_report.exchangeResultCode = (exchange_report.SUCCESS)
                exchange_report.exchangeResultMessage = (exchange_report.STORJ_REPORT_SHARD_UPLOADED)
                self.set_current_status("Sending Exchange Report for shard " + str(chapters + 1))
                # self.storj_engine.storj_client.send_exchange_report(exchange_report) # send exchange report
                break



    def file_upload_begin(self):


        self.initialize_upload_queue_table()
        #item = ProgressWidgetItem()
        #self.ui_single_file_upload.shard_queue_table_widget.setItem(1, 1, item)
        #item.updateValue(1)

        #progress.valueChanged.connect(item.updateValue)


        encryption_enabled = True
        self.parametrs = storj.model.StorjParametrs()

        # get temporary files path
        if self.ui_single_file_upload.tmp_path.text() == "":
            self.parametrs.tmpPath = "/tmp/"
        else:
            self.parametrs.tmpPath = self.ui_single_file_upload.tmp_path.text()

        self.configuration = Configuration()



        file_path = "/home/lakewik/config.json"
        bucket_id = "dc4778cc186192af49475b49"
        bname = os.path.split(file_path)[1]

        mime = magic.Magic(mime=True)
        file_mime_type = str(mime.from_file(str(file_path)))

        file_existence_in_bucket = False

        #if self.configuration.sameFileNamePrompt or self.configuration.sameFileHashPrompt:
            #file_existence_in_bucket = self.storj_engine.storj_client.check_file_existence_in_bucket(bucket_id=bucket_id, filepath=file_path) # chech if exist file with same file name

        if file_existence_in_bucket == 1:
            # QInputDialog.getText(self, 'Warning!', 'File with name ' + str(bname) + " already exist in bucket! Please use different name:", "test" )
            print "Same file exist!"


        if self.ui_single_file_upload.encrypt_files_checkbox.isChecked():
            # encrypt file
            self.set_current_status("Encrypting file...")
            file_crypto_tools = FileCrypto()
            file_crypto_tools.encrypt_file("AES", str(file_path), self.parametrs.tmpPath + bname + ".encrypted", "kotecze57") # begin file encryption
            file_path_ready = self.parametrs.tmpPath + bname + ".encrypted"
            file_name_ready_to_shard_upload = bname + ".encrypted"
        else:
            file_path_ready = file_path
            file_name_ready_to_shard_upload = bname

        def get_size(file_like_object):
            return os.stat(file_like_object.name).st_size

        # file_size = get_size(file)
        file_size = os.stat(file_path).st_size
        self.ui_single_file_upload.current_state.setText(
            html_format_begin + "Resolving PUSH token..." + html_format_end)

        push_token = None

        try:
            push_token = self.storj_engine.storj_client.token_create(bucket_id,
                                                                     'PUSH')  # get the PUSH token from Storj Bridge
        except storj.exception.StorjBridgeApiError, e:
            QMessageBox.about(self, "Unhandled PUSH token create exception", "Exception: " + str(e))

        self.ui_single_file_upload.push_token.setText(
            html_format_begin + str(push_token.id) + html_format_end)  # set the PUSH Token

        print push_token.id

        self.ui_single_file_upload.current_state.setText(
            html_format_begin + "Resolving frame for file..." + html_format_end)
        try:
            frame = self.storj_engine.storj_client.frame_create()  # Create file frame
        except storj.exception.StorjBridgeApiError, e:
            QMessageBox.about(self, "Unhandled exception while creating file staging frame", "Exception: " + str(e))

        self.ui_single_file_upload.file_frame_id.setText(html_format_begin + str(frame.id) + html_format_end)

        print frame.id
        # Now encrypt file

        # Now generate shards
        self.set_current_status("Splitting file to shards...")
        shards_manager = model.ShardManager(str(file_path_ready), 1)

        #self.ui_single_file_upload.current_state.setText(html_format_begin + "Generating shards..." + html_format_end)
        # shards_manager._make_shards()
        shards_count = shards_manager.index
        # create file hash
        self.storj_engine.storj_client.logger.debug('file_upload() push_token=%s', push_token)

        # upload shards to frame
        print shards_count
        chapters = 0
        firstiteration = True


        for shard in shards_manager.shards:
            self.createNewShardUploadThread(shard, chapters, frame, file_name_ready_to_shard_upload)
            chapters += 1


        # delete encrypted file

        # hash_sha512_hmac = self.storj_engine.storj_client.get_custom_checksum(file_path)
        hash_sha512_hmac = "dxjcdj"
        def finish_upload(self):
            self.crypto_tools = CryptoTools()
            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Generating SHA5212 HMAC..." + html_format_end)
            hash_sha512_hmac_b64 = self.crypto_tools.prepare_bucket_entry_hmac(shards_manager.shards)
            hash_sha512_hmac = hashlib.sha224(str(hash_sha512_hmac_b64["SHA-512"])).hexdigest()
            print hash_sha512_hmac
            # save

            # import magic
            # mime = magic.Magic(mime=True)
            # mime.from_file(file_path)

            print frame.id
            print "Now upload file"

            data = {
                'x-token': push_token.id,
                'x-filesize': str(file_size),
                'frame': frame.id,
                'mimetype': file_mime_type,
                'filename': str(bname),
                'hmac': {
                    'type': "sha512",
                    # 'value': hash_sha512_hmac["sha512_checksum"]
                    'value': hash_sha512_hmac
                },
            }
            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Adding file to bucket..." + html_format_end)

            success = False
            try:
                response = self.storj_engine.storj_client._request(
                    method='POST', path='/buckets/%s/files' % bucket_id,
                    # files={'file' : file},
                    headers={
                        'x-token': push_token.id,
                        'x-filesize': str(file_size),
                    },
                    json=data,
                )
                success = True
            except storj.exception.StorjBridgeApiError, e:
                QMessageBox.about(self, "Unhandled exception", "Exception: " + str(e))
            if success:
                self.ui_single_file_upload.current_state.setText(
                    html_format_begin + "Upload success! Waiting for user..." + html_format_end)


        self.connect(self, SIGNAL("finishUpload"), lambda: finish_upload(self))
        #self.emit(SIGNAL("finishUpload")) # send signal to save to bucket after all filea are uploaded

        #finish_upload(self)








if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads)
    app = QtGui.QApplication(sys.argv)

    myapp = MainUI()
    initial_window = InitialWindowUI()

    account_manager = AccountManager()
    if account_manager.if_logged_in():
        myapp.show()
    else:
        initial_window.show()

    sys.exit(app.exec_())
