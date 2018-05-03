# -*- coding: utf-8 -*-

"""
/***************************************************************************
 EcosystemServiceValuator
                                 A QGIS plugin
 Calculate ecosystem service values for a given area
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-04-02
        copyright            : (C) 2018 by Phil Ribbens/Key-Log Economics
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

__author__ = 'Phil Ribbens/Key-Log Economics'
__date__ = '2018-04-02'
__copyright__ = '(C) 2018 by Phil Ribbens/Key-Log Economics'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import numpy as np
from numpy import copy
import processing

from os.path import splitext

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsField,
                       QgsFields,
                       QgsFeature,
                       QgsProcessingParameterRasterDestination,
                       QgsRasterFileWriter,
                       QgsProject,
                       QgsProcessingParameterVectorLayer,
                       QgsRasterLayer,
                       QgsProcessingFeatureSource
                       )

import appinter

class CreateEcosystemServiceValuesTableAlgorithm(QgsProcessingAlgorithm):
    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_RASTER_SUMMARY = 'INPUT_RASTER_SUMMARY'
    INPUT_ESV = 'INPUT_ESV'
    OUTPUT_TABLE = 'OUTPUT_TABLE'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm
        """
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_RASTER_SUMMARY,
                self.tr('Input table of raster unique values'),
                [QgsProcessing.TypeFile]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ESV,
                self.tr('Input table of ESV research data'),
                [QgsProcessing.TypeFile]
            )
        )

        # Add a feature sink for the output data table
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_TABLE,
                self.tr('Output ESV table')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        log = feedback.setProgressText

        #Create feature sources out of both input CSVs so we can use their contents
        raster_summary_source = self.parameterAsSource(parameters, self.INPUT_RASTER_SUMMARY, context)
        esv_source = self.parameterAsSource(parameters, self.INPUT_ESV, context)

        esv_source_field_names = esv_source.fields().names()
        if len(esv_source_field_names) != 4:
            feedback.reportError("The ESV data table should have 4 columns, the one you input has " + str(len(esv_source_field_names)))
            log("")
            return {self.OUTPUT_TABLE : ''}
        else:
            log("ESV data table has 4 columns. Check")

        nlcd_codes = [11,12,21,22,23,24,31,41,42,43,51,52,71,72,73,74,81,82,90,95]
        esv_source_col1_values = esv_source.uniqueValues(0)
        if all(int(value) in nlcd_codes for value in esv_source_col1_values):
            log("All of the values in column 1 of the ESV data table are NLCD codes. Check")
        else:
            feedback.reportError("Not all of the values in column 1 of the ESV data table are NLCD codes. Your dataset should only include valid NLCD codes.")
            feedback.pushDebugInfo("Here is the list of all the possible NLCD codes: " + str(nlcd_codes))
            log("")
            return {self.OUTPUT_TABLE : ''}

        # Create list of fields (i.e. column names) for the output CSV
        # Start with fields from the raster input csv
        stat_fields = QgsFields()
        # Then append new fields for the min, max, and mean of each unique
        # ecosystem service (i.e. water, recreation, etc)
        unique_eco_services = esv_source.uniqueValues(2)
        for eco_service in unique_eco_services:
            min_field_str = eco_service.lower() + "_" + "min"
            mean_field_str = eco_service.lower() + "_" + "mean"
            max_field_str = eco_service.lower() + "_" + "max"
            stat_fields.append(QgsField(min_field_str))
            stat_fields.append(QgsField(mean_field_str))
            stat_fields.append(QgsField(max_field_str))
        # Then append three more columns for the totals
        stat_fields.append(QgsField("total_min"))
        stat_fields.append(QgsField("total_mean"))
        stat_fields.append(QgsField("total_max"))

        sink_fields = raster_summary_source.fields()
        sink_fields.extend(stat_fields)

        # Create the feature sink for the output data table, i.e. the place where we're going to start
        # putting our output data. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_TABLE, context, sink_fields)

        result = {self.OUTPUT_TABLE : dest_id}

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / raster_summary_source.featureCount() if raster_summary_source.featureCount() else 0

        raster_summary_features = raster_summary_source.getFeatures()

        area_units_conversion_factor = 0.0001

        # Calculate mins, maxs, and means for each unique combo of NLCD code and
        # ecosystem service and append values to output table
        for raster_summary_current, raster_summary_feature in enumerate(raster_summary_features):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            nlcd_code = raster_summary_feature.attributes()[0]
            pixel_count = raster_summary_feature.attributes()[1]
            area = raster_summary_feature.attributes()[2]

            new_feature = QgsFeature(sink_fields)
            new_feature.setAttribute(0, nlcd_code)
            new_feature.setAttribute(1, pixel_count)
            new_feature.setAttribute(2, area)

            total_min = 0
            total_mean = 0
            total_max = 0

            for field_index in stat_fields.allAttributesList():
                es = stat_fields.field(field_index).name().split("_")
                es_name = es[0].lower()
                es_stat = es[1]

                if es_name != "total":
                    values_list = []
                    esv_features = esv_source.getFeatures()

                    for esv_feature in esv_features:
                        if esv_feature.attributes()[0] == nlcd_code:
                            if esv_feature.attributes()[2].lower() == es_name:
                                values_list.append(float(esv_feature.attributes()[3]))

                    values_array = np.asarray(values_list)

                    if values_array.shape[0] > 0:
                        if es_stat == "min":
                            nlcd_min = float(area) * area_units_conversion_factor * float(np.amin(values_array))
                            total_min = total_min + nlcd_min
                            new_feature.setAttribute(field_index + 3, nlcd_min)
                        elif es_stat == "mean":
                            nlcd_mean = float(area) * area_units_conversion_factor * float(np.mean(values_array))
                            total_mean = total_mean + nlcd_mean
                            new_feature.setAttribute(field_index + 3, nlcd_mean)
                        elif es_stat == "max":
                            nlcd_max = float(area) * area_units_conversion_factor * float(np.amax(values_array))
                            total_max = total_max + nlcd_max
                            new_feature.setAttribute(field_index + 3, nlcd_max)
                elif es_name == "total":
                    if es_stat == "min":
                        new_feature.setAttribute(field_index + 3, total_min)
                    if es_stat == "mean":
                        new_feature.setAttribute(field_index + 3, total_mean)
                    if es_stat == "max":
                        new_feature.setAttribute(field_index + 3, total_max)

            # Add a feature in the sink
            sink.addFeature(new_feature, QgsFeatureSink.FastInsert)

            # Update the progress bar
            feedback.setProgress(int(raster_summary_current * total))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return result

    def mapValues(self, numpy_array, dictionary):
        output_array = copy(numpy_array)
        for key, value in dictionary.items():
            output_array[numpy_array==key] = value
        return output_array

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Create ESV table'

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
        return 'Ecosystem service valuator'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateEcosystemServiceValuesTableAlgorithm()
