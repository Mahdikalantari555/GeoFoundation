# RS Research Notes

This document covers vegetation indices and crop monitoring.

## NDVI

NDVI (Normalized Difference Vegetation Index) is computed as:

    (NIR - Red) / (NIR + Red)

Values range from -1 to 1. Healthy vegetation has high NDVI.

## Sentinel-2

Sentinel-2 provides multispectral imagery with 13 bands including:
- B02 (Blue, 10m)
- B03 (Green, 10m)
- B04 (Red, 10m)
- B08 (NIR, 10m)

## Crop Stress Detection

Crop stress can be detected by monitoring NDVI time series.
A decline in NDVI over consecutive Sentinel-2 acquisitions indicates stress.
