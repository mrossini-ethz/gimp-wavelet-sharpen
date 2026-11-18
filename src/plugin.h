/*
 * Wavelet sharpen GIMP plugin
 *
 * plugin.h
 * Copyright 2008 by Marco Rossini
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2+
 * as published by the Free Software Foundation.
 */

#ifndef __PLUGIN_H__
#define __PLUGIN_H__

#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <libgimp/gimp.h>
#include <libgimp/gimpui.h>
#include <glib/gi18n.h>

#define PLUG_IN_PROC "plug-in-wavelet-sharpen"
#define PLUG_IN_BINARY "wavelet-sharpen"

#define MAX2(x,y) ((x) > (y) ? (x) : (y))
#define MIN2(x,y) ((x) < (y) ? (x) : (y))
#define CLIP(x,min,max) MAX2((min), MIN2((x), (max)))

/* Tool-tips */
#define TT_AMOUNT _("Adjusts the amount of sharpening applied.")
#define TT_RADIUS _("Adjusts the radius of the sharpening. For very unsharp images it is recommended to use higher values. Default is 0.5.")
#define TT_LUMINANCE _("Sharpens luminance only (YCbCr luminance channel). This avoids color artifacts to appear and makes the sharpening faster. Colour sharpness in natural images is not critical for the human eye.")

/* the settings of one sharpening run, read from the procedure config */
typedef struct
{
  double sharpen_amount;
  double sharpen_radius;
  gboolean luminance_only;
} wavelet_settings;

void wavelet_sharpen (float *fimg[3], unsigned int width,
			     unsigned int height, double amount,
			     double radius, float a, float b);
gboolean sharpen (GimpDrawable * drawable, GimpPreview * preview,
		  const wavelet_settings * settings, GError ** error);
void settings_from_config (GimpProcedureConfig * config,
			   wavelet_settings * settings);
void rgb2ycbcr (float *r, float *g, float *b);
void ycbcr2rgb (float *y, float *cb, float *cr);
gboolean user_interface (GimpProcedure * procedure,
			 GimpProcedureConfig * config,
			 GimpDrawable * drawable);

#endif /* __PLUGIN_H__ */
