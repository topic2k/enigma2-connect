param([switch]$SocialOnly)
# Reproducible vector construction and PNG export; Windows PowerShell 5.1 / System.Drawing.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$source = @'
using System;
using System.IO;
using System.Text;
using System.Globalization;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.Collections.Generic;

public static class EnigmaBrandExport {
    static string N(float n) { return n.ToString("0.###", CultureInfo.InvariantCulture); }
    static GraphicsPath Receiver() {
        var p = new GraphicsPath(FillMode.Alternate);
        p.StartFigure();
        p.AddLine(64,242,816,242); p.AddBezier(816,242,851,242,880,271,880,306);
        p.AddLine(880,306,880,416); p.AddBezier(880,416,880,451,851,480,816,480);
        p.AddLine(816,480,816,490); p.AddBezier(816,490,816,499,809,506,800,506);
        p.AddLine(800,506,752,506); p.AddBezier(752,506,743,506,736,499,736,490);
        p.AddLine(736,490,736,480); p.AddLine(736,480,144,480);
        p.AddLine(144,480,144,490); p.AddBezier(144,490,144,499,137,506,128,506);
        p.AddLine(128,506,80,506); p.AddBezier(80,506,71,506,64,499,64,490);
        p.AddLine(64,490,64,480); p.AddBezier(64,480,29,480,0,451,0,416);
        p.AddLine(0,416,0,306); p.AddBezier(0,306,0,271,29,242,64,242);
        p.CloseFigure();
        // Display and remote body are true transparent negative space.
        p.AddPath(RoundRect(96,344,320,40,20),false);
        p.StartFigure(); p.AddBezier(558,242,620,264,684,264,746,242);
        p.AddLine(746,242,746,386);
        p.AddBezier(746,386,746,438,704,480,652,480);
        p.AddBezier(652,480,600,480,558,438,558,386);
        p.AddLine(558,386,558,242); p.CloseFigure();
        return p;
    }
    static GraphicsPath RoundRect(float x,float y,float w,float h,float r) {
        var p = new GraphicsPath();
        p.AddArc(x,y,r*2,r*2,180,90); p.AddArc(x+w-r*2,y,r*2,r*2,270,90);
        p.AddArc(x+w-r*2,y+h-r*2,r*2,r*2,0,90); p.AddArc(x,y+h-r*2,r*2,r*2,90,90);
        p.CloseFigure(); return p;
    }
    static GraphicsPath RemoteTop() {
        var p = new GraphicsPath(FillMode.Alternate);
        p.AddLine(618,0,686,0); p.AddBezier(686,0,719,0,746,27,746,60);
        p.AddLine(746,60,746,242); p.AddBezier(746,242,684,264,620,264,558,242);
        p.AddLine(558,242,558,60); p.AddBezier(558,60,558,27,585,0,618,0); p.CloseFigure();
        p.AddEllipse(592,74,120,120); return p;
    }
    static GraphicsPath Buttons() {
        var p = new GraphicsPath();
        p.AddEllipse(616,98,72,72); p.AddEllipse(631,289,42,42); p.AddEllipse(631,355,42,42);
        return p;
    }
    static string PathData(GraphicsPath p) {
        var b = new StringBuilder(); var pts=p.PathPoints; var types=p.PathTypes;
        for(int i=0;i<pts.Length;i++) {
            int type=types[i]&7;
            if(type==0) b.Append("M"+N(pts[i].X)+" "+N(pts[i].Y));
            else if(type==1) b.Append("L"+N(pts[i].X)+" "+N(pts[i].Y));
            else if(type==3) {
                b.Append("C"+N(pts[i].X)+" "+N(pts[i].Y)+" "+N(pts[i+1].X)+" "+N(pts[i+1].Y)+" "+N(pts[i+2].X)+" "+N(pts[i+2].Y)); i+=2;
            }
            if((types[i]&128)!=0) b.Append("Z");
        }
        return b.ToString();
    }
    static GraphicsPath Transform(GraphicsPath p, float scale, float x, float y) {
        var copy=(GraphicsPath)p.Clone();
        using(var m=new Matrix(scale,0,0,scale,x,y)) copy.Transform(m);
        return copy;
    }
    static void Png(string file, List<GraphicsPath> paths, Color[] colors, RectangleF view, int w,int h, Color? backgroundColor = null) {
        const int supersample=3;
        using(var hi=new Bitmap(w*supersample,h*supersample,PixelFormat.Format32bppArgb)) {
            using(var g=Graphics.FromImage(hi)) {
                g.Clear(backgroundColor ?? Color.Transparent); g.SmoothingMode=SmoothingMode.AntiAlias;
                g.CompositingQuality=CompositingQuality.HighQuality;
                g.ScaleTransform(w*supersample/view.Width,h*supersample/view.Height);
                g.TranslateTransform(-view.X,-view.Y);
                for(int i=0;i<paths.Count;i++) using(var brush=new SolidBrush(colors[i])) g.FillPath(brush,paths[i]);
            }
            using(var output=new Bitmap(w,h,PixelFormat.Format32bppArgb)) {
                using(var g=Graphics.FromImage(output)) {
                    g.Clear(backgroundColor ?? Color.Transparent); g.CompositingMode=backgroundColor.HasValue ? CompositingMode.SourceOver : CompositingMode.SourceCopy;
                    g.InterpolationMode=InterpolationMode.HighQualityBicubic; g.PixelOffsetMode=PixelOffsetMode.HighQuality;
                    using(var attrs=new ImageAttributes()) {
                        attrs.SetWrapMode(WrapMode.TileFlipXY);
                        g.DrawImage(hi,new Rectangle(0,0,w,h),0,0,hi.Width,hi.Height,GraphicsUnit.Pixel,attrs);
                    }
                }
                output.Save(file,ImageFormat.Png);
            }
        }
    }
    static void Svg(string file,List<GraphicsPath> paths,Color[] colors,RectangleF v) {
        var b=new StringBuilder();
        b.Append("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\""+N(v.X)+" "+N(v.Y)+" "+N(v.Width)+" "+N(v.Height)+"\" role=\"img\" aria-label=\"Enigma2 Connect\">\n<title>Enigma2 Connect</title>\n");
        for(int i=0;i<paths.Count;i++) b.Append("<path fill=\""+ColorTranslator.ToHtml(colors[i])+"\" fill-rule=\"evenodd\" d=\""+PathData(paths[i])+"\"/>\n");
        b.Append("</svg>\n"); File.WriteAllText(file,b.ToString(),new UTF8Encoding(false));
    }

    public static void Social(string sourceDir, string outputDir) {
        Directory.CreateDirectory(outputDir);
        using(var fonts=new PrivateFontCollection()) {
            fonts.AddFontFile(Path.Combine(sourceDir,"Poppins-ExtraBold.ttf"));
            var family=fonts.Families[0];
            var style=family.IsStyleAvailable(FontStyle.Regular)?FontStyle.Regular:FontStyle.Bold;
            using(var receiver=Receiver()) using(var remote=RemoteTop()) using(var buttons=Buttons())
            using(var word=new GraphicsPath()) using(var background=new GraphicsPath()) {
                word.AddString("Enigma2 Connect",family,(int)style,142,new PointF(0,0),StringFormat.GenericTypographic);
                var bounds=word.GetBounds();
                float scale=960f/bounds.Width;
                using(var matrix=new Matrix(scale,0,0,scale,160-bounds.X*scale,414-bounds.Y*scale)) word.Transform(matrix);
                background.AddRectangle(new RectangleF(0,0,1280,640));
                var paths=new List<GraphicsPath> {
                    background,Transform(receiver,.5f,420,90),
                    Transform(remote,.5f,420,90),Transform(buttons,.5f,420,90),word
                };
                var navy=ColorTranslator.FromHtml("#15346F");
                var colors=new[]{Color.White,navy,ColorTranslator.FromHtml("#006BFF"),navy,navy};
                var view=new RectangleF(0,0,1280,640);
                Png(Path.Combine(outputDir,"social-preview.png"),paths,colors,view,1280,640,Color.White);
                Svg(Path.Combine(sourceDir,"social-preview.svg"),paths,colors,view);
                for(int i=1;i<=3;i++)paths[i].Dispose();
            }
        }
    }
    public static void Run(string sourceDir,string brandDir) {
        Directory.CreateDirectory(brandDir);
        using(var fonts=new PrivateFontCollection()) {
            fonts.AddFontFile(Path.Combine(sourceDir,"Poppins-ExtraBold.ttf"));
            var receiver=Receiver(); var remote=RemoteTop(); var buttons=Buttons();
            var word=new GraphicsPath();
            var family=fonts.Families[0];
            var style=family.IsStyleAvailable(FontStyle.Regular)?FontStyle.Regular:FontStyle.Bold;
            word.AddString("Enigma2 Connect",family,(int)style,142,new PointF(0,0),StringFormat.GenericTypographic);
            var bounds=word.GetBounds();
            using(var matrix=new Matrix()) {matrix.Translate(390-bounds.X,63-bounds.Y);word.Transform(matrix);}
            var iconPaths=new List<GraphicsPath>{receiver,remote,buttons};
            var logoPaths=new List<GraphicsPath>{Transform(receiver,.4f,0,0),Transform(remote,.4f,0,0),Transform(buttons,.4f,0,0),word};
            var iconView=new RectangleF(-20,-207,920,920);
            var logoView=new RectangleF(-4,-4,word.GetBounds().Right+8,212);
            foreach(bool dark in new[]{false,true}) {
                string prefix=dark?"dark_":"";
                Color ink=ColorTranslator.FromHtml(dark?"#E5EEFF":"#15346F");
                Color blue=ColorTranslator.FromHtml(dark?"#4192FF":"#006BFF");
                var iconColors=new[]{ink,blue,ink}; var logoColors=new[]{ink,blue,ink,ink};
                Svg(Path.Combine(sourceDir,prefix+"icon.svg"),iconPaths,iconColors,iconView);
                Svg(Path.Combine(sourceDir,prefix+"logo.svg"),logoPaths,logoColors,logoView);
                foreach(int size in new[]{256,512}) {
                    string suffix=size==512?"@2x":"";
                    Png(Path.Combine(brandDir,prefix+"icon"+suffix+".png"),iconPaths,iconColors,iconView,size,size);
                    // Logos: 128px and 256px tall, exact same aspect ratio.
                    int height=size/2, width=(int)Math.Round(logoView.Width/logoView.Height*height);
                    Png(Path.Combine(brandDir,prefix+"logo"+suffix+".png"),logoPaths,logoColors,logoView,width,height);
                }
            }
            foreach(var p in logoPaths)p.Dispose(); foreach(var p in iconPaths)p.Dispose();
        }
    }
}
'@
Add-Type -TypeDefinition $source -ReferencedAssemblies System.Drawing
$sourceDir = Join-Path $PSScriptRoot 'source'
$projectDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$brandDir = Join-Path $projectDir 'custom_components\enigma2_connect\brand'
if (!$SocialOnly) { [EnigmaBrandExport]::Run($sourceDir,$brandDir) }
[EnigmaBrandExport]::Social($sourceDir,$PSScriptRoot)
Get-Item -LiteralPath (Join-Path $PSScriptRoot 'social-preview.png') | Select-Object Name,Length
