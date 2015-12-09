# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UniumPlugin
                                 A QGIS plugin
 The plugin for Unium
                              -------------------
        begin                : 2015-11-30
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Ivan Medvedev/MapCrap
        email                : medvedev.ivan@mail.ru
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QVariant
from PyQt4.QtGui import QAction, QIcon, QFileDialog, QTableWidgetItem, qApp
from PyQt4.QtCore import pyqtSlot,SIGNAL,SLOT
from qgis.core import *
from qgis.gui import *
from lxml import etree
# Initialize Qt resources from file resources.py
import resources, os, sqlite3, shutil, datetime, json, math

# Import the code for the DockWidget
from mcqp_unium_dockwidget import UniumPluginDockWidget
import os.path


class UniumPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UniumPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&UniumPlugin')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'UniumPlugin')
        self.toolbar.setObjectName(u'UniumPlugin')

        #print "** INITIALIZING UniumPlugin"

        self.pluginIsActive = False
        self.dockwidget = None
        
        # initialize dict for saving data about importing sml
        self.sml_data = {}
        
        # initialize layers data
        self.categories = {}
        self.layers = {}
        self.selected_id = u''

        # default configuration
        default_config = """{"files_folder": "",
                            "write_block": 50
                            }
                            """


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('UniumPlugin', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/UniumPlugin/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Unium'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING UniumPlugin"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD UniumPlugin"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&UniumPlugin'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""
        
        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING UniumPlugin"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = UniumPluginDockWidget()
                self.dockwidget.catbrwsButton.clicked.connect(self.select_cat_file)
                self.dockwidget.marksbrwsButton.clicked.connect(self.select_marks_file)
                self.dockwidget.dbbrwsButton.clicked.connect(self.select_db_file)
                self.dockwidget.loadSASButton.clicked.connect(self.loadSASButton_clicked)
                self.dockwidget.layersBox.currentIndexChanged.connect(self.selected_layer_changed)
                self.dockwidget.ffbrwsButton.clicked.connect(self.select_filefolder_clicked)
                self.dockwidget.wrblkBox.valueChanged.connect(self.wrblkBox_value_changed)
                self.dockwidget.savesetButton.clicked.connect(self.savesetButton_clicked)
                self.dockwidget.loadsetButton.clicked.connect(self.loadsetButton_clicked)
                #self.dockwidget.layersBox.connect(self.dockwidget.layersBox,SIGNAL("currentIndexChanged(int)"),self.dockwidget,SLOT("self.selected_layer_changed(int)"))
                
            self.dockwidget.layersBox.currentIndex = 1
            
            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            self.getSettings()
            self.updateSettingsUI()
            self.get_project_settings()
            self.update_layers_list()
            
            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

    #--------------------------------------------------------------------------

    def getSettings(self):
        config_file = os.path.join(os.path.dirname(__file__),'mcqp_unium_config.json')
        msg = u"Конфигурационный файл отсутствует. Будет загружена конфигурация по-умолчанию"
        if os.path.exists(config_file):
            try:
                conf = open(config_file,'r')
                self.config = json.load(conf)
                conf.close()
                i_msg = u"Конфигурация загружена"
                self.iface.messageBar().pushMessage("Info", i_msg, level=QgsMessageBar.INFO, duration=7)
                QgsMessageLog.logMessage(i_msg, level=QgsMessageLog.INFO)
                return
            except Exception,err:
                msg = u"Ошибка при загрузке конфигурационного файла: %s. Будет загружена конфигурация по-умолчанию" % err
        else:
            self.iface.messageBar().pushMessage("Warning", msg, level=QgsMessageBar.WARNING, duration=7)
            QgsMessageLog.logMessage(msg, level=QgsMessageLog.WARNING)

    def setSettings(self):
        config_file = os.path.join(os.path.dirname(__file__),'mcqp_unium_config.json')
        if os.path.exists(config_file):
            try:
                conf = open(config_file,'w')
                json.dump(self.config,conf)
                conf.close()
                i_msg = u"Конфигурация сохранена"
                self.iface.messageBar().pushMessage("Info", i_msg, level=QgsMessageBar.INFO, duration=7)
                QgsMessageLog.logMessage(i_msg, level=QgsMessageLog.INFO)
                return
            except Exception,err:
                msg = u"Ошибка при записи конфигурационного файла: %s." % err
                self.iface.messageBar().pushMessage("Warning", msg, level=QgsMessageBar.WARNING, duration=7)
                QgsMessageLog.logMessage(msg, level=QgsMessageLog.WARNING)

    def get_project_settings(self):
        # Читаем список категорий в формате {<id>:"<категория>"}
        self.categories = json.loads(QgsProject.instance().readEntry("UniumPlugin", "categories", "{}")[0])

    def set_project_settings(self):
        QgsProject.instance().writeEntry("UniumPlugin", "categories", json.dumps(self.categories))

    def updateSettingsUI(self):
        self.dockwidget.filefolderEdit.setText(self.config['files_folder'])
        self.dockwidget.wrblkBox.setValue(self.config['write_block'])

    #--------------------------------------------------------------------------

    @staticmethod
    def rec_get_layer_path(root,layer_id,path):
        check = False
        for node in root.children():
            if isinstance(node,QgsLayerTreeGroup):
                (check,path) = UniumPlugin.rec_get_layer_path(node,layer_id,path)
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
                (check,path) = UniumPlugin.rec_get_layer_path(node,layer_id,path)
                if check:
                    path.append(root.name())
                    break
            elif isinstance(node,QgsLayerTreeLayer):
                if node.layerId() == layer_id:
                    path.append(root.name())
        path.reverse()
        return chr(92).join([p for p in path if len(p) > 0])

    def get_layers(self):
        self.layers = {}
        for lyr in self.iface.legendInterface().layers():
            if isinstance(lyr, QgsVectorLayer):
                path = UniumPlugin.get_layer_path(QgsProject.instance().layerTreeRoot(),lyr.id())
                self.layers[lyr.id()] = {'name': lyr.name(),
                                    'subset': lyr.subsetString(),
                                    'path': path,
                                    'full_name':chr(92).join([path,lyr.name()])}

    def update_layers_list(self):
        list_items = []
        self.dockwidget.layersBox.clear()
        self.get_layers()
        for lid in self.layers.keys():
            list_items.append(self.layers[lid].get('full_name',''))
        list_items.sort()
        self.dockwidget.layersBox.addItems(list_items)

    def update_TView(self):
        if self.selected_id in self.layers.keys():
            self.dockwidget.layersBox.enabled = False
            for lyr in self.iface.legendInterface().layers():
                if isinstance(lyr, QgsVectorLayer) and lyr.id() == self.selected_id:
                    attrs_names = [a.name() for a in lyr.fields()]
                    attrs_values = [[feat[i] for i in xrange(len(attrs_names))] for feat in lyr.getFeatures()]
                    self.dockwidget.tableView.setRowCount(len(attrs_values))
                    self.dockwidget.tableView.setColumnCount(len(attrs_names))
                    self.dockwidget.tableView.setHorizontalHeaderLabels(attrs_names)
                    for row in xrange(len(attrs_values)):
                        for col in xrange(len(attrs_names)):
                            item = QTableWidgetItem(u'%s' % attrs_values[row][col])
                            self.dockwidget.tableView.setItem(row,col,item)
                    break
            self.dockwidget.layersBox.enabled = True

    # create lyr for category
    @staticmethod
    def create_catlyr(uri,chain,cat_id):
        cat_lyr = QgsVectorLayer(uri.uri(), chain, 'spatialite')
        cat_lyr.setSubsetString('("cat_id" = %s)' % cat_id)
        cat_lyr.setCustomProperty("cat_filter", cat_id)
        cat_lyr.setCustomProperty("name_filter", "")
        cat_lyr.setCustomProperty("descr_filter", "")
        return cat_lyr

    @staticmethod
    def set_subsets(lyr,cat_id,name = '',descr = ''):
        subset_str = u'("cat_id" = %s)' % cat_id
        cat_lyr.setCustomProperty("cat_filter", cat_id)
        cat_lyr.setCustomProperty("name_filter", name)
        if name:
            subset_str += u' & ("name" like \'%{1}%\')'.format(name)
        
        if descr:
            subset_str += u' & ("descr" like \'%{1}%\')'.format(descr)
        lyr.setSubsetString(subset_str)
    
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
        cur.execute('CREATE TABLE %s (id INTEGER NOT NULL PRIMARY KEY,name TEXT,descr TEXT,sign TEXT,cat_id INTEGER)'% table_name)
        con.commit()
        cur.execute("SELECT AddGeometryColumn(?,'shape', 4326, 'POINT', 'XY')",(table_name,))
        con.commit()
        con.close()
        return table_name
    
    def ParseSML(self):
        """Parse categorymarks.sml to dictionary and make layers tree"""
        try:
            self.dockwidget.sasprogressBar.value = 0
            if not os.path.exists(self.sml_data['db_file']):
                empty_db = os.path.join(os.path.dirname(__file__),'empty.sqlite')
                if os.path.exists(empty_db):
                    shutil.copy2(empty_db,self.sml_data['db_file'])
                else:
                    UniumPlugin.create_db(self.sml_data['db_file'])
                QgsMessageLog.logMessage(u'Новая база создана', level=QgsMessageLog.INFO)
            self.dockwidget.sasprogressBar.setValue(25)
            qApp.processEvents()

            self.sml_data['table'] = UniumPlugin.create_table(self.sml_data['db_file'],self.sml_data['table'])
            QgsMessageLog.logMessage(u'Новая таблица в базе создана', level=QgsMessageLog.INFO)
            self.dockwidget.sasprogressBar.setValue(50)
            qApp.processEvents()

            QgsMessageLog.logMessage(u'Начинаю загружать метки', level=QgsMessageLog.INFO)

            marksf = open(self.sml_data['marks_file'],'r')
            tree = etree.XML(marksf.read().decode('cp1251'))
            marksf.close()

            nodes = tree.xpath('/DATAPACKET/ROWDATA/ROW')

            uri = QgsDataSourceURI()
            uri.setDatabase(self.sml_data['db_file'])
            uri.setDataSource('', self.sml_data['table'], 'shape')

            lyr = QgsVectorLayer(uri.uri(),self.sml_data['table'],'spatialite')
            pr = lyr.dataProvider()
            lyr.startEditing()

            nodes_count = len(nodes)
            groups = [self.config["write_block"] for i in xrange(nodes_count/self.config["write_block"])]
            groups.append(nodes_count%self.config["write_block"])

            prgrs_interval = int(math.ceil(nodes_count/25.0))

            features = []
            group_idx = 0
            f_idx = 0
            position = 50

            for node in nodes:
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(float(node.get('lonL')),float(node.get('LatB')))))
                fields = pr.fields()
                feature.setFields(fields)
                feature.setAttribute('name',node.get('name'))
                feature.setAttribute('descr',node.get('descr'))
                feature.setAttribute('sign',node.get('picname'))
                feature.setAttribute('cat_id',int(node.get('categoryid')))
                features.append(feature)
                if len(features) == groups[group_idx]:
                    pr.addFeatures(features)
                    features = []
                    group_idx+=1
                f_idx+=1
                if f_idx%prgrs_interval == 0:
                    position+=1
                    self.dockwidget.sasprogressBar.setValue(position)
                    qApp.processEvents()

            lyr.commitChanges()
            self.dockwidget.sasprogressBar.setValue(75)
            qApp.processEvents()
            
            lyr = None
            
            QgsMessageLog.logMessage(u'Метки записаны в БД', level=QgsMessageLog.INFO)
            QgsMessageLog.logMessage(u'Начинаем добавлять слои', level=QgsMessageLog.INFO)
        
            catf = open(self.sml_data['cat_file'],'r')
            tree = etree.XML(catf.read().decode('cp1251'))
            catf.close()
            
            nodes = tree.xpath('/DATAPACKET/ROWDATA/ROW')
            
            root = QgsProject.instance().layerTreeRoot()
            root.removeAllChildren()
            QgsMapLayerRegistry.instance().removeAllMapLayers()

            self.categories = {}
            
            for node in nodes:
                chain = node.get('name').split(chr(92))

                self.categories[int(node.get('id'))] = node.get('name')
                
                # Create sublayers for category
                c_root = root
                for i in xrange(len(chain)-1):
                    c_node = c_root.findGroup(chain[i])
                    if not c_node:
                        c_node = c_root.addGroup(chain[i])
                    c_root = c_node
                
                cat_lyr = QgsVectorLayer(uri.uri(), chain[len(chain)-1], 'spatialite')
                cat_lyr.setSubsetString('("cat_id" = \'%s\')' % node.get('id'))
                QgsMapLayerRegistry.instance().addMapLayer(cat_lyr,False)
                c_root.addLayer(cat_lyr)

            self.set_project_settings()
            self.iface.mapCanvas().mapRenderer().setDestinationCrs(QgsCoordinateReferenceSystem(3857, QgsCoordinateReferenceSystem.EpsgCrsId))
                
            QgsMessageLog.logMessage(u'Слои созданы', level=QgsMessageLog.INFO)
            self.dockwidget.sasprogressBar.setValue(100)
            qApp.processEvents()
        except Exception, err:
            self.iface.messageBar().pushMessage("Error", u"Что-то случилось: %s" % err, level=QgsMessageBar.CRITICAL, duration=7)
            QgsMessageLog.logMessage(u'%s' % err, level=QgsMessageLog.CRITICAL)
    
    ##### Events methods #####
    def select_cat_file(self):
        self.sml_data['cat_file'] = QFileDialog.getOpenFileName(self.dockwidget, "Select Categorymarks.sml file ", os.path.dirname(self.sml_data.get('marks_file','')),"*.sml")
        self.dockwidget.catfileEdit.setText(self.sml_data['cat_file'])
    
    def select_marks_file(self):
        self.sml_data['marks_file'] = QFileDialog.getOpenFileName(self.dockwidget, "Select marks.sml file ", os.path.dirname(self.sml_data.get('cat_file','')),"*.sml")
        self.dockwidget.marksfileEdit.setText(self.sml_data['marks_file'])
        
    def select_db_file(self):
        self.sml_data['db_file'] = QFileDialog.getSaveFileName(self.dockwidget, "Select SpatiaLite database file ", os.path.dirname(self.sml_data.get('cat_file','')),"*.sqlite",QFileDialog.DontConfirmOverwrite)
        self.dockwidget.dbfileEdit.setText(self.sml_data['db_file'])
        
    def loadSASButton_clicked(self):
        self.sml_data['table'] = self.dockwidget.tbldbEdit.text()
        if self.sml_data.get('cat_file',None) and self.sml_data.get('marks_file',None) and self.sml_data.get('db_file', None) and self.sml_data.get('table', None):
            self.ParseSML()
            self.update_layers_list()

    def select_filefolder_clicked(self):
        sel_folder = QFileDialog.getExistingDirectory(self.dockwidget, "Select folder for saving files", self.config.get('files_folder',os.getenv("HOME")),QFileDialog.ShowDirsOnly)
        self.dockwidget.filefolderEdit.setText(sel_folder)
        self.config['files_folder'] = sel_folder

    @pyqtSlot(int)
    def wrblkBox_value_changed(self):
        self.config['write_block'] = self.dockwidget.wrblkBox.value()

    @pyqtSlot(int)
    def selected_layer_changed(self, idx):
        for lid in self.layers.keys():
            if self.layers[lid].get('full_name','') == self.dockwidget.layersBox.currentText():
                self.selected_id = lid
                QgsMessageLog.logMessage(u'Текущий слой: %s' % lid, level=QgsMessageLog.INFO)
                self.update_TView()

    def loadsetButton_clicked(self):
        self.getSettings()
        self.updateSettingsUI()

    def savesetButton_clicked(self):
        self.setSettings()