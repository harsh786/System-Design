import java.util.*;

// ============================================================
// EXAMPLE 1: Shape Visitor
// ============================================================

// Element interface
interface Shape {
    void accept(ShapeVisitor visitor);
}

// Concrete Elements
class Circle implements Shape {
    private final double radius;

    public Circle(double radius) { this.radius = radius; }
    public double getRadius() { return radius; }

    @Override
    public void accept(ShapeVisitor visitor) {
        // Double dispatch: the element calls back the visitor with 'this'
        // 1st dispatch: polymorphic call to accept() resolves element type
        // 2nd dispatch: visitor.visitCircle(this) resolves operation type
        visitor.visitCircle(this);
    }
}

class Rectangle implements Shape {
    private final double width, height;

    public Rectangle(double width, double height) {
        this.width = width;
        this.height = height;
    }
    public double getWidth() { return width; }
    public double getHeight() { return height; }

    @Override
    public void accept(ShapeVisitor visitor) {
        visitor.visitRectangle(this);
    }
}

class Triangle implements Shape {
    private final double a, b, c; // sides

    public Triangle(double a, double b, double c) {
        this.a = a; this.b = b; this.c = c;
    }
    public double getA() { return a; }
    public double getB() { return b; }
    public double getC() { return c; }

    @Override
    public void accept(ShapeVisitor visitor) {
        visitor.visitTriangle(this);
    }
}

class CompoundShape implements Shape {
    private final List<Shape> children = new ArrayList<>();

    public void add(Shape shape) { children.add(shape); }
    public List<Shape> getChildren() { return children; }

    @Override
    public void accept(ShapeVisitor visitor) {
        visitor.visitCompoundShape(this);
    }
}

// Visitor interface
interface ShapeVisitor {
    void visitCircle(Circle circle);
    void visitRectangle(Rectangle rectangle);
    void visitTriangle(Triangle triangle);
    void visitCompoundShape(CompoundShape compound);
}

// Concrete Visitor 1: Area Calculator
class AreaCalculator implements ShapeVisitor {
    private double totalArea = 0;

    public double getTotalArea() { return totalArea; }
    public void reset() { totalArea = 0; }

    @Override
    public void visitCircle(Circle c) {
        totalArea += Math.PI * c.getRadius() * c.getRadius();
    }

    @Override
    public void visitRectangle(Rectangle r) {
        totalArea += r.getWidth() * r.getHeight();
    }

    @Override
    public void visitTriangle(Triangle t) {
        double s = (t.getA() + t.getB() + t.getC()) / 2;
        totalArea += Math.sqrt(s * (s - t.getA()) * (s - t.getB()) * (s - t.getC()));
    }

    @Override
    public void visitCompoundShape(CompoundShape compound) {
        for (Shape child : compound.getChildren()) {
            child.accept(this);
        }
    }
}

// Concrete Visitor 2: Perimeter Calculator
class PerimeterCalculator implements ShapeVisitor {
    private double totalPerimeter = 0;

    public double getTotalPerimeter() { return totalPerimeter; }
    public void reset() { totalPerimeter = 0; }

    @Override
    public void visitCircle(Circle c) {
        totalPerimeter += 2 * Math.PI * c.getRadius();
    }

    @Override
    public void visitRectangle(Rectangle r) {
        totalPerimeter += 2 * (r.getWidth() + r.getHeight());
    }

    @Override
    public void visitTriangle(Triangle t) {
        totalPerimeter += t.getA() + t.getB() + t.getC();
    }

    @Override
    public void visitCompoundShape(CompoundShape compound) {
        for (Shape child : compound.getChildren()) {
            child.accept(this);
        }
    }
}

// Concrete Visitor 3: Drawing Exporter (SVG-like)
class DrawingExporter implements ShapeVisitor {
    private final StringBuilder sb = new StringBuilder();

    public String getResult() { return sb.toString(); }

    @Override
    public void visitCircle(Circle c) {
        sb.append(String.format("<circle r=\"%.1f\" />\n", c.getRadius()));
    }

    @Override
    public void visitRectangle(Rectangle r) {
        sb.append(String.format("<rect width=\"%.1f\" height=\"%.1f\" />\n", r.getWidth(), r.getHeight()));
    }

    @Override
    public void visitTriangle(Triangle t) {
        sb.append(String.format("<polygon sides=\"%.1f,%.1f,%.1f\" />\n", t.getA(), t.getB(), t.getC()));
    }

    @Override
    public void visitCompoundShape(CompoundShape compound) {
        sb.append("<g>\n");
        for (Shape child : compound.getChildren()) {
            child.accept(this);
        }
        sb.append("</g>\n");
    }
}

// Concrete Visitor 4: XML Exporter
class XMLExporter implements ShapeVisitor {
    private final StringBuilder sb = new StringBuilder();
    private int indent = 0;

    public String getResult() { return sb.toString(); }

    private String tabs() { return "  ".repeat(indent); }

    @Override
    public void visitCircle(Circle c) {
        sb.append(tabs()).append(String.format("<circle radius=\"%.2f\" />\n", c.getRadius()));
    }

    @Override
    public void visitRectangle(Rectangle r) {
        sb.append(tabs()).append(String.format("<rectangle width=\"%.2f\" height=\"%.2f\" />\n", r.getWidth(), r.getHeight()));
    }

    @Override
    public void visitTriangle(Triangle t) {
        sb.append(tabs()).append(String.format("<triangle a=\"%.2f\" b=\"%.2f\" c=\"%.2f\" />\n", t.getA(), t.getB(), t.getC()));
    }

    @Override
    public void visitCompoundShape(CompoundShape compound) {
        sb.append(tabs()).append("<compound>\n");
        indent++;
        for (Shape child : compound.getChildren()) {
            child.accept(this);
        }
        indent--;
        sb.append(tabs()).append("</compound>\n");
    }
}

// ============================================================
// EXAMPLE 2: File System Visitor
// ============================================================

interface FileElement {
    void accept(FileVisitor visitor);
    String getName();
    long getSize();
}

class TextFile implements FileElement {
    private final String name;
    private final long size;
    private final String content;

    public TextFile(String name, long size, String content) {
        this.name = name; this.size = size; this.content = content;
    }
    public String getName() { return name; }
    public long getSize() { return size; }
    public String getContent() { return content; }

    @Override
    public void accept(FileVisitor visitor) { visitor.visitTextFile(this); }
}

class ImageFile implements FileElement {
    private final String name;
    private final long size;
    private final int width, height;

    public ImageFile(String name, long size, int width, int height) {
        this.name = name; this.size = size; this.width = width; this.height = height;
    }
    public String getName() { return name; }
    public long getSize() { return size; }
    public int getWidth() { return width; }
    public int getHeight() { return height; }

    @Override
    public void accept(FileVisitor visitor) { visitor.visitImageFile(this); }
}

class VideoFile implements FileElement {
    private final String name;
    private final long size;
    private final int durationSeconds;

    public VideoFile(String name, long size, int durationSeconds) {
        this.name = name; this.size = size; this.durationSeconds = durationSeconds;
    }
    public String getName() { return name; }
    public long getSize() { return size; }
    public int getDurationSeconds() { return durationSeconds; }

    @Override
    public void accept(FileVisitor visitor) { visitor.visitVideoFile(this); }
}

// File Visitor interface
interface FileVisitor {
    void visitTextFile(TextFile file);
    void visitImageFile(ImageFile file);
    void visitVideoFile(VideoFile file);
}

// Size Calculator visitor
class SizeCalculator implements FileVisitor {
    private long totalSize = 0;

    public long getTotalSize() { return totalSize; }

    @Override
    public void visitTextFile(TextFile file) { totalSize += file.getSize(); }
    @Override
    public void visitImageFile(ImageFile file) { totalSize += file.getSize(); }
    @Override
    public void visitVideoFile(VideoFile file) { totalSize += file.getSize(); }
}

// Search Visitor
class SearchVisitor implements FileVisitor {
    private final String keyword;
    private final List<String> results = new ArrayList<>();

    public SearchVisitor(String keyword) { this.keyword = keyword; }
    public List<String> getResults() { return results; }

    @Override
    public void visitTextFile(TextFile file) {
        if (file.getContent().contains(keyword)) {
            results.add("Found '" + keyword + "' in text file: " + file.getName());
        }
    }

    @Override
    public void visitImageFile(ImageFile file) {
        if (file.getName().contains(keyword)) {
            results.add("Found '" + keyword + "' in image filename: " + file.getName());
        }
    }

    @Override
    public void visitVideoFile(VideoFile file) {
        if (file.getName().contains(keyword)) {
            results.add("Found '" + keyword + "' in video filename: " + file.getName());
        }
    }
}

// Antivirus Scanner visitor
class AntivirusScanner implements FileVisitor {
    private final List<String> threats = new ArrayList<>();

    public List<String> getThreats() { return threats; }

    @Override
    public void visitTextFile(TextFile file) {
        if (file.getContent().contains("eval(") || file.getContent().contains("<script>")) {
            threats.add("THREAT: Suspicious script in " + file.getName());
        }
    }

    @Override
    public void visitImageFile(ImageFile file) {
        if (file.getSize() > 50_000_000) {
            threats.add("WARNING: Unusually large image " + file.getName());
        }
    }

    @Override
    public void visitVideoFile(VideoFile file) {
        if (file.getName().endsWith(".exe.mp4")) {
            threats.add("THREAT: Disguised executable " + file.getName());
        }
    }
}

// ============================================================
// Main - Demonstration
// ============================================================
public class VisitorPattern {
    public static void main(String[] args) {
        System.out.println("=== VISITOR DESIGN PATTERN ===\n");

        // --- Example 1: Shapes ---
        System.out.println("--- Example 1: Shape Visitors ---\n");

        List<Shape> shapes = List.of(
            new Circle(5),
            new Rectangle(4, 6),
            new Triangle(3, 4, 5)
        );

        CompoundShape compound = new CompoundShape();
        compound.add(new Circle(2));
        compound.add(new Rectangle(3, 3));

        // Adding new operations WITHOUT modifying Shape classes
        AreaCalculator areaCalc = new AreaCalculator();
        PerimeterCalculator perimCalc = new PerimeterCalculator();
        DrawingExporter exporter = new DrawingExporter();
        XMLExporter xmlExporter = new XMLExporter();

        for (Shape s : shapes) {
            s.accept(areaCalc);
            s.accept(perimCalc);
            s.accept(exporter);
            s.accept(xmlExporter);
        }
        compound.accept(areaCalc);
        compound.accept(exporter);
        compound.accept(xmlExporter);

        System.out.printf("Total area: %.2f\n", areaCalc.getTotalArea());
        System.out.printf("Total perimeter: %.2f\n", perimCalc.getTotalPerimeter());
        System.out.println("\nSVG Export:\n" + exporter.getResult());
        System.out.println("XML Export:\n" + xmlExporter.getResult());

        // --- Example 2: File System ---
        System.out.println("--- Example 2: File System Visitors ---\n");

        List<FileElement> files = List.of(
            new TextFile("readme.txt", 1024, "Hello world, this is a readme file."),
            new TextFile("malicious.html", 2048, "<script>eval('hack')</script>"),
            new ImageFile("photo.png", 5_000_000, 1920, 1080),
            new VideoFile("tutorial.mp4", 500_000_000, 3600),
            new VideoFile("virus.exe.mp4", 1024, 10)
        );

        SizeCalculator sizeCalc = new SizeCalculator();
        SearchVisitor search = new SearchVisitor("readme");
        AntivirusScanner antivirus = new AntivirusScanner();

        for (FileElement f : files) {
            f.accept(sizeCalc);
            f.accept(search);
            f.accept(antivirus);
        }

        System.out.printf("Total size: %,d bytes\n\n", sizeCalc.getTotalSize());

        System.out.println("Search results:");
        search.getResults().forEach(r -> System.out.println("  " + r));

        System.out.println("\nAntivirus scan:");
        antivirus.getThreats().forEach(t -> System.out.println("  " + t));

        System.out.println("\n--- Double Dispatch Explained ---");
        System.out.println("1. Client calls shape.accept(visitor) -> dispatches on Shape type");
        System.out.println("2. Shape calls visitor.visitXxx(this) -> dispatches on Visitor type");
        System.out.println("Result: correct method chosen based on BOTH element and visitor types");
    }
}
