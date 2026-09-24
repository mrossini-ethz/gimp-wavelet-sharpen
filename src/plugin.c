/*
 * Wavelet sharpen GIMP plugin
 *
 * plugin.c
 * Copyright 2008 by Marco Rossini
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2+
 * as published by the Free Software Foundation.
 */

#include "plugin.h"

typedef struct _WaveletSharpen WaveletSharpen;
typedef struct _WaveletSharpenClass WaveletSharpenClass;

struct _WaveletSharpen
{
  GimpPlugIn parent_instance;
};

struct _WaveletSharpenClass
{
  GimpPlugInClass parent_class;
};

#define WAVELET_SHARPEN_TYPE (wavelet_sharpen_plug_in_get_type ())

GType wavelet_sharpen_plug_in_get_type (void);

static GList *wavelet_sharpen_query_procedures (GimpPlugIn * plug_in);
static GimpProcedure *wavelet_sharpen_create_procedure (GimpPlugIn * plug_in,
							const gchar * name);
static GimpValueArray *wavelet_sharpen_run (GimpProcedure * procedure,
					    GimpRunMode run_mode,
					    GimpImage * image,
					    GimpDrawable ** drawables,
					    GimpProcedureConfig * config,
					    gpointer run_data);

G_DEFINE_TYPE (WaveletSharpen, wavelet_sharpen_plug_in, GIMP_TYPE_PLUG_IN)

GIMP_MAIN (WAVELET_SHARPEN_TYPE)

static void
wavelet_sharpen_plug_in_class_init (WaveletSharpenClass * klass)
{
  GimpPlugInClass *plug_in_class = GIMP_PLUG_IN_CLASS (klass);

  plug_in_class->query_procedures = wavelet_sharpen_query_procedures;
  plug_in_class->create_procedure = wavelet_sharpen_create_procedure;
}

static void
wavelet_sharpen_plug_in_init (WaveletSharpen * wavelet_sharpen)
{
}

static GList *
wavelet_sharpen_query_procedures (GimpPlugIn * plug_in)
{
  return g_list_append (NULL, g_strdup (PLUG_IN_PROC));
}

static GimpProcedure *
wavelet_sharpen_create_procedure (GimpPlugIn * plug_in, const gchar * name)
{
  GimpProcedure *procedure;

  if (strcmp (name, PLUG_IN_PROC))
    return NULL;

  procedure = gimp_image_procedure_new (plug_in, name,
					GIMP_PDB_PROC_TYPE_PLUGIN,
					wavelet_sharpen_run, NULL, NULL);

  gimp_procedure_set_image_types (procedure, "RGB*, GRAY*");
  gimp_procedure_set_sensitivity_mask (procedure,
				       GIMP_PROCEDURE_SENSITIVE_DRAWABLE);

  gimp_procedure_set_menu_label (procedure, _("_Wavelet sharpen ..."));
  gimp_procedure_add_menu_path (procedure, "<Image>/Filters/Enhance");

  gimp_procedure_set_documentation (procedure,
				    _("Sharpens the image using wavelets."),
				    _("Sharpens the image using wavelets."),
				    name);
  gimp_procedure_set_attribution (procedure, "Marco Rossini",
				  "Copyright 2008 Marco Rossini", "2008");

  /* the arguments keep the names of the GIMP 2 version for scripts */
  gimp_procedure_add_double_argument (procedure, "amount", _("_Amount"),
				      TT_AMOUNT, 0.0, 10.0, 0.0,
				      G_PARAM_READWRITE);
  gimp_procedure_add_double_argument (procedure, "radius", _("Ra_dius"),
				      TT_RADIUS, 0.0, 2.0, 0.5,
				      G_PARAM_READWRITE);
  gimp_procedure_add_boolean_argument (procedure, "luminance",
				       _("Sharpen lu_minance only"),
				       TT_LUMINANCE, TRUE,
				       G_PARAM_READWRITE);

  return procedure;
}

void
settings_from_config (GimpProcedureConfig * config,
		      wavelet_settings * settings)
{
  g_object_get (config,
		"amount", &settings->sharpen_amount,
		"radius", &settings->sharpen_radius,
		"luminance", &settings->luminance_only, NULL);
}

static GimpValueArray *
wavelet_sharpen_run (GimpProcedure * procedure, GimpRunMode run_mode,
		     GimpImage * image, GimpDrawable ** drawables,
		     GimpProcedureConfig * config, gpointer run_data)
{
  GimpDrawable *drawable;
  wavelet_settings settings;
  GError *error = NULL;

  gegl_init (NULL, NULL);

  if (gimp_core_object_array_get_length ((GObject **) drawables) != 1)
    {
      g_set_error (&error, GIMP_PLUG_IN_ERROR, 0,
		   _("Procedure '%s' only works with one drawable."),
		   PLUG_IN_PROC);
      return gimp_procedure_new_return_values (procedure,
					       GIMP_PDB_CALLING_ERROR, error);
    }
  drawable = drawables[0];

  /* run GUI if in interactive mode */
  if (run_mode == GIMP_RUN_INTERACTIVE
      && !user_interface (procedure, config, drawable))
    return gimp_procedure_new_return_values (procedure, GIMP_PDB_CANCEL,
					     NULL);

  settings_from_config (config, &settings);

  if (!sharpen (drawable, NULL, &settings, &error))
    return gimp_procedure_new_return_values (procedure,
					     GIMP_PDB_EXECUTION_ERROR, error);

  if (run_mode != GIMP_RUN_NONINTERACTIVE)
    gimp_displays_flush ();

  return gimp_procedure_new_return_values (procedure, GIMP_PDB_SUCCESS,
					   NULL);
}
