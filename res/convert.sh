#!/bin/sh

for size in 16 20 22 24 32 36 40 48 64 72 96 128 192 256; do
	mkdir -p icons/hicolor/${size}x$size/apps/
	convert tpm2-algtest.png -resize ${size}x$size icons/hicolor/${size}x$size/apps/tpm2-algtest.png
done
