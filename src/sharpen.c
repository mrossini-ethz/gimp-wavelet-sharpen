/*
 * Wavelet sharpen GIMP plugin
 *
 * sharpen.c
 * Copyright 2008 by Marco Rossini
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2+
 * as published by the Free Software Foundation.
 */

#include "plugin.h"

/* number of rows transferred from and to GIMP at once */
#define STRIP_HEIGHT 64

/* progress fractions of reading and writing, the rest is sharpening */
#define PROGRESS_READ 0.1
#define PROGRESS_WRITE 0.1

/* The algorithm works on non-linear values, as it did on 8-bit sRGB data
   before. Use the matching float format in the colour space of the
   drawable, so that any precision is processed without loss. */
static const Babl *
get_float_format (GimpDrawable * drawable)
{
  const Babl *space = babl_format_get_space (gimp_drawable_get_format
					     (drawable));
  const char *name;

  if (gimp_drawable_is_rgb (drawable))
    name = gimp_drawable_has_alpha (drawable) ? "R'G'B'A float"
      : "R'G'B' float";
  else
    name = gimp_drawable_has_alpha (drawable) ? "Y'A float" : "Y' float";

  return babl_format_with_space (name, space);
}

/* only float images may hold values outside of [0,1] */
static gboolean
drawable_is_float (GimpDrawable * drawable)
{
  const Babl *type = babl_format_get_type (gimp_drawable_get_format
					   (drawable), 0);

  return type == babl_type ("half") || type == babl_type ("float")
    || type == babl_type ("double");
}

static void
free_planes (float **planes, gint n)
{
  gint i;

  for (i = 0; i < n; i++)
    g_free (planes[i]);
}

gboolean
sharpen (GimpDrawable * drawable, GimpPreview * preview,
	 const wavelet_settings * settings, GError ** error)
{
  float *fimg[4] = { NULL, NULL, NULL, NULL };
  float *buffer[3] = { NULL, NULL, NULL };
  float *strip, val[4];
  GeglBuffer *src_buffer, *dest_buffer;
  const Babl *format;
  gint x1, y1, width, height, y, c, channels, colour_channels, rows;
  gsize i, size, bufsize;
  gboolean luminance, clip_colour, alloc_ok;
  gint channels_to_sharpen, channels_sharpened;
  double progress_step;

  if (preview)
    {
      gimp_preview_get_position (preview, &x1, &y1);
      gimp_preview_get_size (preview, &width, &height);
    }
  else if (!gimp_drawable_mask_intersect (drawable, &x1, &y1, &width,
					  &height))
    return TRUE;

  if (width <= 0 || height <= 0)
    return TRUE;

  format = get_float_format (drawable);
  channels = babl_format_get_n_components (format);
  /* the alpha channel is never sharpened */
  colour_channels = (channels % 2) ? channels : channels - 1;
  luminance = colour_channels == 3 && settings->luminance_only;
  clip_colour = !drawable_is_float (drawable);

  channels_to_sharpen = settings->sharpen_amount > 0
    ? (luminance ? 1 : colour_channels) : 0;

  /* nothing to do: leave the drawable exactly as it is */
  if (!preview && channels_to_sharpen == 0)
    return TRUE;

  /* allocate one plane per channel plus two for the wavelet transform;
     the wavelet code counts pixels in unsigned int */
  if (!g_size_checked_mul (&size, width, height) || size > G_MAXUINT
      || !g_size_checked_mul (&bufsize, size, sizeof (float)))
    {
      g_set_error (error, GIMP_PLUG_IN_ERROR, 0,
		   _("Image dimensions too large: width %d x height %d"),
		   width, height);
      return FALSE;
    }
  alloc_ok = TRUE;
  for (c = 0; c < channels; c++)
    alloc_ok = alloc_ok && (fimg[c] = g_try_malloc (bufsize)) != NULL;
  alloc_ok = alloc_ok && (buffer[1] = g_try_malloc (bufsize)) != NULL;
  alloc_ok = alloc_ok && (buffer[2] = g_try_malloc (bufsize)) != NULL;
  strip = alloc_ok ? g_try_malloc ((gsize) width * STRIP_HEIGHT * channels
				   * sizeof (float)) : NULL;
  if (!strip)
    {
      free_planes (fimg, channels);
      free_planes (buffer + 1, 2);
      g_set_error (error, GIMP_PLUG_IN_ERROR, 0,
		   _("There was not enough memory to complete the "
		     "operation."));
      return FALSE;
    }

  progress_step = (1.0 - PROGRESS_READ - PROGRESS_WRITE)
    / MAX2 (channels_to_sharpen, 1);

  /* read the image from GIMP */
  if (!preview)
    gimp_progress_init (_("Wavelet sharpening..."));
  src_buffer = gimp_drawable_get_buffer (drawable);
  for (y = 0; y < height; y += STRIP_HEIGHT)
    {
      rows = MIN2 (STRIP_HEIGHT, height - y);
      gegl_buffer_get (src_buffer, GEGL_RECTANGLE (x1, y1 + y, width, rows),
		       1.0, format, strip, GEGL_AUTO_ROWSTRIDE,
		       GEGL_ABYSS_NONE);

      /* do the colour model conversion in [0:255] and scale for
         sharpening */
      for (i = 0; i < (gsize) rows * width; i++)
	{
	  for (c = 0; c < channels; c++)
	    val[c] = strip[i * channels + c] * 255.0;
	  if (luminance)
	    rgb2ycbcr (&(val[0]), &(val[1]), &(val[2]));
	  for (c = 0; c < channels; c++)
	    fimg[c][y * width + i] = val[c] / 255.0;
	}
      if (!preview)
	gimp_progress_update (PROGRESS_READ * (y + rows) / height);
    }
  g_object_unref (src_buffer);

  /* sharpen the channels individually */
  channels_sharpened = 0;
  for (c = 0; c < colour_channels && settings->sharpen_amount > 0; c++)
    {
      double a, b;

      if (luminance && c > 0)
	continue;
      buffer[0] = fimg[c];
      a = PROGRESS_READ + channels_sharpened * progress_step;
      b = preview ? 0.0 : progress_step;
      wavelet_sharpen (buffer, width, height, settings->sharpen_amount,
		       settings->sharpen_radius, a, b);
      channels_sharpened++;
    }

  /* retransform the image data */
  for (c = 0; c < channels; c++)
    for (i = 0; i < size; i++)
      fimg[c][i] = fimg[c][i] * 255;

  /* convert to RGB if necessary */
  if (luminance)
    for (i = 0; i < size; i++)
      ycbcr2rgb (&(fimg[0][i]), &(fimg[1][i]), &(fimg[2][i]));

  /* clip the values and scale back to [0:1] */
  for (c = 0; c < channels; c++)
    {
      gboolean clip = clip_colour || c >= colour_channels;

      for (i = 0; i < size; i++)
	fimg[c][i] = (clip ? CLIP (fimg[c][i], 0, 255) : fimg[c][i]) / 255.0;
    }

  if (preview)
    {
      /* the preview is drawn from 8-bit data of the drawable layout */
      guchar *line = g_malloc (size * channels);

      for (i = 0; i < size; i++)
	for (c = 0; c < channels; c++)
	  line[i * channels + c] = (guchar)
	    (CLIP (fimg[c][i], 0.0, 1.0) * 255.0 + 0.5);
      gimp_preview_draw_buffer (preview, line, width * channels);
      g_free (line);
    }
  else
    {
      /* write the image back to GIMP */
      dest_buffer = gimp_drawable_get_shadow_buffer (drawable);
      for (y = 0; y < height; y += STRIP_HEIGHT)
	{
	  rows = MIN2 (STRIP_HEIGHT, height - y);
	  for (i = 0; i < (gsize) rows * width; i++)
	    for (c = 0; c < channels; c++)
	      strip[i * channels + c] = fimg[c][y * width + i];
	  gegl_buffer_set (dest_buffer,
			   GEGL_RECTANGLE (x1, y1 + y, width, rows), 0,
			   format, strip, GEGL_AUTO_ROWSTRIDE);
	  gimp_progress_update (1.0 - PROGRESS_WRITE
				+ PROGRESS_WRITE * (y + rows) / height);
	}
      g_object_unref (dest_buffer);

      gimp_drawable_merge_shadow (drawable, TRUE);
      gimp_drawable_update (drawable, x1, y1, width, height);
    }

  g_free (strip);
  free_planes (fimg, channels);
  free_planes (buffer + 1, 2);

  return TRUE;
}
