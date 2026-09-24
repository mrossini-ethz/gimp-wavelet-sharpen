/*
 * Wavelet sharpen GIMP plugin
 *
 * interface.c
 * Copyright 2008 by Marco Rossini
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2+
 * as published by the Free Software Foundation.
 */

#include "plugin.h"

static void
preview_update (GimpPreview * preview, GimpProcedureConfig * config)
{
  GimpDrawable *drawable = g_object_get_data (G_OBJECT (config), "drawable");
  wavelet_settings settings;

  settings_from_config (config, &settings);
  sharpen (drawable, preview, &settings, NULL);
}

gboolean
user_interface (GimpProcedure * procedure, GimpProcedureConfig * config,
		GimpDrawable * drawable)
{
  GimpProcedureDialog *dialog;
  GtkWidget *preview, *widget;
  gboolean run;

  gimp_ui_init (PLUG_IN_BINARY);

  dialog = GIMP_PROCEDURE_DIALOG (gimp_procedure_dialog_new
				  (procedure, config, _("Wavelet sharpen")));

  /* prepare the preview */
  preview = gimp_procedure_dialog_get_drawable_preview (dialog, "preview",
							drawable);
  g_object_set_data (G_OBJECT (config), "drawable", drawable);
  g_signal_connect (preview, "invalidated", G_CALLBACK (preview_update),
		    config);
  g_signal_connect_swapped (config, "notify",
			    G_CALLBACK (gimp_preview_invalidate), preview);

  /* prepare the amount and radius sliders */
  widget = gimp_procedure_dialog_get_spin_scale (dialog, "amount", 1.0);
  gtk_spin_button_set_digits (GTK_SPIN_BUTTON (widget), 1);
  gtk_spin_button_set_increments (GTK_SPIN_BUTTON (widget), 0.1, 1.0);
  widget = gimp_procedure_dialog_get_spin_scale (dialog, "radius", 1.0);
  gtk_spin_button_set_digits (GTK_SPIN_BUTTON (widget), 2);
  gtk_spin_button_set_increments (GTK_SPIN_BUTTON (widget), 0.01, 0.1);

  /* luminance only is meaningful for colour images only */
  if (gimp_drawable_is_rgb (drawable))
    gimp_procedure_dialog_fill (dialog, "preview", "amount", "radius",
				"luminance", NULL);
  else
    gimp_procedure_dialog_fill (dialog, "preview", "amount", "radius", NULL);

  run = gimp_procedure_dialog_run (dialog);
  gtk_widget_destroy (GTK_WIDGET (dialog));

  return run;
}
