# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UniumPlugin
                                 A QGIS plugin
 The plugin for Unium
                             -------------------
        begin                : 2015-11-30
        copyright            : (C) 2015 by Ivan Medvedev/MapCrap
        email                : medvedev.ivan@mail.ru
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load UniumPlugin class from file UniumPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .mcqp_unium import UniumPlugin
    return UniumPlugin(iface)
