# -*- coding: utf-8 -*-

import resources, os, sqlite3, shutil, datetime, json
from qgis.core import *
from qgis.gui import *
from lxml import etree

class mcqp_unium:
    def __init__(self):
        # default configuration
        self.default_config = """{"files_folder": "",
                            "write_block": 50
                            }
                           """
        # configuration
        self.config = self.default_config

        # data for import sml
        self.sml_data = {}

        # layers info
        self.layers = {}
        self.categories = {}

        # selected layer id
        self.selected_id = u''

    # ------------------ CONFIG --------------------
    def getSettings(self):
        config_file = os.path.join(os.path.dirname(__file__),'mcqp_unium_config.json')
        msg = u"Конфигурационный файл отсутствует. Будет загружена конфигурация по-умолчанию"
        e_level = QgsMessageBar.WARNING
        if os.path.exists(config_file):
            try:
                conf = open(config_file,'r')
                self.config = json.load(conf)
                conf.close()
                msg = u"Конфигурация загружена"
                e_level = QgsMessageBar.INFO
            except Exception,err:
                msg = u"Ошибка при загрузке конфигурационного файла: %s. Будет загружена конфигурация по-умолчанию" % err
        else:
            self.config = self.default_config
        return (msg,e_level)

    def setSettings(self):
        config_file = os.path.join(os.path.dirname(__file__),'mcqp_unium_config.json')
        if os.path.exists(config_file):
            try:
                conf = open(config_file,'w')
                json.dump(self.config,conf)
                conf.close()
                return (u"Конфигурация сохранена", QgsMessageBar.INFO)
            except Exception,err:
                return (u"Ошибка при записи конфигурационного файла: %s." % err, QgsMessageBar.WARNING)

    # -------------------- LAYERS -----------------------
    @staticmethod
    def rec_get_layer_path(root,layer_id,path):
        check = False
        for node in root.children():
            if isinstance(node,QgsLayerTreeGroup):
                (check,path) = mcqp_unium.rec_get_layer_path(node,layer_id,path)
                if check:
                    path.append(root.name())
                    return (check,path)
            elif isinstance(node,QgsLayerTreeLayer):
                if node.layerId() == layer_id:
                    path.append(root.name())
                    check = True
        return (check,path)

    @staticmethod
    def get_layer_path(root,layer_id):
        path = []
        for node in root.children():
            if isinstance(node,QgsLayerTreeGroup):
                check = False
                (check,path) = mcqp_unium.rec_get_layer_path(node,layer_id,path)
                if check:
                    path.append(root.name())
                    break
            elif isinstance(node,QgsLayerTreeLayer):
                if node.layerId() == layer_id:
                    path.append(root.name())
        path.reverse()
        return chr(92).join([p for p in path if len(p) > 0])

    # iface - QgsInterface, qp_instance - QgsProject.instance()
    def get_layers(self, iface, qp_instance):
        self.layers = {}
        for lyr in iface.legendInterface().layers():
            if isinstance(lyr, QgsVectorLayer):
                path = mcqp_unium.get_layer_path(qp_instance.layerTreeRoot(),lyr.id())
                self.layers[lyr.id()] = {'name': lyr.name(),
                                    'subset': lyr.subsetString(),
                                    'path': path,
                                    'full_name':chr(92).join([path,lyr.name()])}

    # -------------- SpatiaLite -------------------
    @staticmethod
    def create_db(db_file):
        con = sqlite3.connect(db_file)
        cur = con.cursor()
        con.enable_load_extension(True)
        con.execute("SELECT load_extension('mod_spatialite.dll')")
        sql = "SELECT InitSpatialMetadata(1,'WGS84')"
        cur.execute(sql)
        con.close()

    @staticmethod
    def create_table(db_file,table_name):
        con = sqlite3.connect(db_file)
        cur = con.cursor()
        con.enable_load_extension(True)
        con.execute("SELECT load_extension('mod_spatialite.dll')")
        count = cur.execute("select count(name) from sqlite_master where type='table' and name = ?",(table_name,))
        if count.fetchall()[0][0] > 0:
            table_name += '_%s' % datetime.datetime.now().strftime('%Y%m%d_%H%M')
        cur.execute('CREATE TABLE %s (id INTEGER NOT NULL PRIMARY KEY,name TEXT,descr TEXT,sign TEXT,cat_id TEXT)'% table_name)
        con.commit()
        cur.execute("SELECT AddGeometryColumn(?,'shape', 4326, 'POINT', 'XY')",(table_name,))
        con.commit()
        con.close()
        return table_name