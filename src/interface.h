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

/* amount/radius frame */
extern GtkObject *amount_adj[2];

/* dialog */
extern GtkWidget *preview;
