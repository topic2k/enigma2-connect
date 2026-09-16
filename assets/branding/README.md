# Branding-Quellen / Branding sources

## Deutsch

Dieser Ordner enthält die weiterhin benötigten Quellen des ausgewählten Motivs
„Integriert“: Receiver und Fernbedienung als gemeinsames Symbol. Die früheren
Entwürfe und Auswahlprotokolle gehören zum lokalen Dokumentationsarchiv.

- `source/`: Logo-/Icon-SVGs und Social-Preview-SVG, Poppins ExtraBold und der zugehörige
  [SIL-OFL-1.1-Lizenztext](source/OFL-Poppins.txt).
- `export.ps1`: reproduzierbarer Export unter Windows PowerShell 5.1 mit System.Drawing.
- Die acht fertigen PNGs liegen unter
  [custom_components/enigma2_connect/brand](../../custom_components/enigma2_connect/brand/).

Aus dem Projektstamm ausführen:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File assets/branding/export.ps1
```

Der Export überschreibt die SVGs und PNGs; Änderungen anschließend prüfen.
Icons: 256/512 Pixel quadratisch. Logos: 1016 × 128 beziehungsweise 2032 × 256
Pixel. Jeweils helle und dunkle Variante, mit echter Alpha-Transparenz.
Die SVG-Wortmarke besteht aus Pfaden; nur der Neu-Export benötigt die Schrift.
Herkunft und Hinweise stehen in [NOTICE](../../NOTICE).

### GitHub Social Preview

[Social Preview herunterladen](social-preview.png) · [SVG-Quelle](source/social-preview.svg)

1280 × 640 Pixel, deckender weißer Hintergrund: Gerätesymbol mittig,
darunter die Wortmarke. Das PNG ist für den manuellen Upload in GitHub
als Social Preview vorgesehen und gehört nicht zu den acht HA-Brand-Dateien.

Nur dieses Bild neu exportieren:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File assets/branding/export.ps1 -SocialOnly
```

## English

This folder holds the active sources for the selected “Integrated” design:
a receiver and remote forming one symbol. Earlier concepts and selection records
belong to the local documentation archive.

- `source/`: logo/icon SVGs and the social-preview SVG, Poppins ExtraBold and its
  [SIL OFL 1.1 license](source/OFL-Poppins.txt).
- `export.ps1`: reproducible export using Windows PowerShell 5.1 and System.Drawing.
- The eight finished PNGs are in
  [custom_components/enigma2_connect/brand](../../custom_components/enigma2_connect/brand/).

Run the command above from the project root. Export overwrites SVGs and PNGs;
review the results afterwards. Icons are 256/512 pixels square; logos are
1016 × 128 or 2032 × 256 pixels. Each has light and dark variants with alpha
transparency. SVG wordmarks use paths; only re-exporting requires the font.
See [NOTICE](../../NOTICE) for attribution.

### GitHub social preview

[Download social preview](social-preview.png) · [SVG source](source/social-preview.svg)

1280 × 640 pixels on opaque white, with the device symbol centered above the
wordmark. The PNG is intended for manual upload as the GitHub social preview
and is separate from the eight HA brand files.
Use the export command with `-SocialOnly` to regenerate only this image.
The default export also regenerates the social preview.
