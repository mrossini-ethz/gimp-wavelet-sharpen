/* 
 * Wavelet sharpen GIMP plugin
 * 
 * wavelet-sharpen.c
 * Copyright 2008 by Marco Rossini
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2+
 * as published by the Free Software Foundation.
 * 
 * Instructions:
 * compile with gimptool, eg. 'gimptool-2.0 --install wavelet-sharpen.c'
 */

#include "plugin.h"

/* declare all widgets global to make things a lot easier */

/* colour mode frame */
extern GtkWidget *lum_toggle;

/* amount/radius frame */
extern GtkWidget *amount_label[2];
extern GtkWidget *amount_spin[2];
extern GtkWidget *amount_hbox[2];
extern GtkWidget *amount_scale[2];
extern GtkObject *amount_adj[2];
extern GtkWidget *amount_vbox;

/* reset buttons */
extern GtkWidget *reset_button;
extern GtkWidget *button_hbox;

/* dialog */
extern GtkWidget *dialog; 
extern GtkWidget *dialog_vbox;
extern GtkWidget *preview;


