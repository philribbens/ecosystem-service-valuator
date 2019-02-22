# -*- coding: utf-8 -*-

"""
/***************************************************************************
 EcoValuator
                                 A QGIS plugin
 Calculate ecosystem service values for a given area
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-04-02
        copyright            : (C) 2018 by Key-Log Economics
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

__author__ = 'Key-Log Economics'
__date__ = '2018-04-02'
__copyright__ = '(C) 2018 by Key-Log Economics'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import csv
import processing
import numpy



from PyQt5.QtGui import *


from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterString,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingOutputLayerDefinition,
                       QgsRasterLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterRasterDestination,
                       QgsProject,
                       QgsPrintLayout,
                       QgsLayoutItemMap,
                       QgsUnitTypes,
                       QgsLayoutPoint,
                       QgsLayoutSize,
                       QgsLayoutItemLegend,
                       QgsLayoutItemLabel,
                       QgsLayerTree,
                       QgsRasterBandStats
                       )

#from qgis.core import *

from qgis.utils import *


__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))



class CreatePrintLayoutAndExportMap(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_VECTOR = 'INPUT_VECTOR'
    INPUT_TITLE = 'INPUT_TITLE'
    INPUT_SUBTITLE = 'INPUT_SUBTITLE'
    INPUT_CREDIT_TEXT = 'INPUT_CREDIT_TEXT'
    INPUT_CREDIT_TEXT_DEFAULT = "Default Credit Text"
    
    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm
        """
        #Add String as input
        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_TITLE,
                self.tr('Input title string (Optional)'),
                " "                                         #this is in place of making the dialog box "optional". Instead just gives default value as blank string
            )
        )

        #Add String as input
        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_SUBTITLE,
                self.tr('Input Subtitle (this should be returned from the ESV choice in step 2)(Optional)'),
                " "
            )
        )

        #Add String as input
        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_CREDIT_TEXT,
                self.tr('Input Credit Text (Optional)'),
                " "
            )
        )

    
    def processAlgorithm(self, parameters, context, feedback):
        """This actually does the processing for creating the print layout and exporting as .pdf"""
        #needs all the arguments (self, parameters, context, feedback)
        
        log = feedback.setProgressText
        
        input_title = self.parameterAsString(parameters, self.INPUT_TITLE, context)
        input_subtitle = self.parameterAsString(parameters, self.INPUT_SUBTITLE, context)
        input_credit_text = self.parameterAsString(parameters, self.INPUT_CREDIT_TEXT, context)
        
        log(f"Title: {input_title}")                       


        """This creates a new print layout"""
        project = QgsProject.instance()             
        manager = project.layoutManager()           
        layout = QgsPrintLayout(project)            
        layoutName = input_title                    #layoutName is going to be name of Title

        layouts_list = manager.printLayouts()
        for layout in layouts_list:
            if layout.name() == layoutName:
                manager.removeLayout(layout)
        
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()                 #create default map canvas
        layout.setName(layoutName)
        manager.addLayout(layout)


        """This adds a map item to the Print Layout"""
        map = QgsLayoutItemMap(layout)
        map.setRect(20, 20, 20, 20)  
        
        #Set Extent
        canvas = iface.mapCanvas()
        map.setExtent(canvas.extent())                  #sets map extent to current map canvas
        layout.addLayoutItem(map)

        #Move & Resize
        map.attemptMove(QgsLayoutPoint(5, 27, QgsUnitTypes.LayoutMillimeters))
        map.attemptResize(QgsLayoutSize(239, 178, QgsUnitTypes.LayoutMillimeters))
        
        """Gathers active layers to add to legend"""
        #Checks layer tree objects and stores them in a list. This includes csv tables
        checked_layers = [layer.name() for layer in QgsProject().instance().layerTreeRoot().children() if layer.isVisible()]
        print(f"Adding {checked_layers} to legend." )
        #get map layer objects of checked layers by matching their names and store those in a list
        layersToAdd = [layer for layer in QgsProject().instance().mapLayers().values() if layer.name() in checked_layers]
        root = QgsLayerTree()
        for layer in layersToAdd:
            log(f"Adding {layer.name()} to legend")
            root.addLayer(layer)

        """This adds a legend item to the Print Layout"""
        legend = QgsLayoutItemLegend(layout)
        legend.model().setRootGroup(root)
        layout.addLayoutItem(legend)
        legend.attemptMove(QgsLayoutPoint(246, 5, QgsUnitTypes.LayoutMillimeters))



        results = {}                    #All I know is processAlgorithm wants to return a dictionary
        return results

    def flags(self):
        """
        From documentation: Algorithm is not thread safe and cannot be run in a
        background thread, e.g. algorithms which manipulate the current project,
        layer selections, or with external dependencies which are not thread safe.
        """
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Step 3: Create Print Layout and Export as .pdf'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'EcoValuator'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("This step takes an output raster layer from step 2 as input and automatically produces a finished map output as a .pdf. The output will contain the map (zoomed to the extent of your current screen) and a legend which contains the active layers in the project (***NEEDS WORK***)")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def helpUrl(self):
        """
        Returns the location of the help file for this algorithm. This is the
        location that will be followed when the user clicks the Help button
        in the algorithm's UI.
        """
        return "http://keylogeconomics.com/ecovaluator-help/"

    def createInstance(self):
        return CreatePrintLayoutAndExportMap()
