import java.util.*;

/**
 * Flyweight Design Pattern - Complete Implementation
 * 
 * Demonstrates memory optimization by sharing common state (intrinsic)
 * across many objects while keeping unique state (extrinsic) separate.
 */

// ==================== Example 1: Forest with Trees ====================

// Flyweight Interface
interface TreeType {
    void render(int x, int y);
    String getName();
    String getColor();
    String getTexture();
}

// Concrete Flyweight - shared intrinsic state
class TreeTypeImpl implements TreeType {
    private final String name;      // intrinsic
    private final String color;     // intrinsic
    private final String texture;   // intrinsic (simulates large texture data)

    public TreeTypeImpl(String name, String color, String texture) {
        this.name = name;
        this.color = color;
        this.texture = texture;
    }

    @Override
    public void render(int x, int y) {
        // In real app, this would draw the tree using shared texture at position (x,y)
    }

    @Override
    public String getName() { return name; }

    @Override
    public String getColor() { return color; }

    @Override
    public String getTexture() { return texture; }

    public long getEstimatedSize() {
        // Simulate: name + color + texture bytes
        return 40 + name.length() * 2 + color.length() * 2 + texture.length() * 2;
    }
}

// Flyweight Factory - ensures sharing
class TreeTypeFactory {
    private static final Map<String, TreeTypeImpl> cache = new HashMap<>();

    public static TreeTypeImpl getTreeType(String name, String color, String texture) {
        String key = name + "_" + color + "_" + texture;
        if (!cache.containsKey(key)) {
            cache.put(key, new TreeTypeImpl(name, color, texture));
        }
        return cache.get(key);
    }

    public static int getCacheSize() {
        return cache.size();
    }

    public static void clearCache() {
        cache.clear();
    }
}

// Context - holds extrinsic state + reference to flyweight
class Tree {
    private final int x;           // extrinsic
    private final int y;           // extrinsic
    private final TreeType type;   // reference to shared flyweight

    public Tree(int x, int y, TreeType type) {
        this.x = x;
        this.y = y;
        this.type = type;
    }

    public void render() {
        type.render(x, y);
    }

    public int getX() { return x; }
    public int getY() { return y; }
    public TreeType getType() { return type; }
}

// Client - Forest manages many trees
class Forest {
    private final List<Tree> trees = new ArrayList<>();

    public void plantTree(int x, int y, String name, String color, String texture) {
        TreeType type = TreeTypeFactory.getTreeType(name, color, texture);
        trees.add(new Tree(x, y, type));
    }

    public void render() {
        for (Tree tree : trees) {
            tree.render();
        }
    }

    public int getTreeCount() { return trees.size(); }
    public int getUniqueTypes() { return TreeTypeFactory.getCacheSize(); }
}

// ==================== Example 2: Text Editor Character Formatting ====================

// Flyweight - shared font properties
class Font {
    private final String family;   // intrinsic
    private final int size;        // intrinsic
    private final boolean bold;    // intrinsic
    private final boolean italic;  // intrinsic

    public Font(String family, int size, boolean bold, boolean italic) {
        this.family = family;
        this.size = size;
        this.bold = bold;
        this.italic = italic;
    }

    public String describe() {
        return family + "-" + size + (bold ? "B" : "") + (italic ? "I" : "");
    }
}

// Font Factory
class FontFactory {
    private static final Map<String, Font> cache = new HashMap<>();

    public static Font getFont(String family, int size, boolean bold, boolean italic) {
        String key = family + "_" + size + "_" + bold + "_" + italic;
        if (!cache.containsKey(key)) {
            cache.put(key, new Font(family, size, bold, italic));
        }
        return cache.get(key);
    }

    public static int getCacheSize() { return cache.size(); }
    public static void clearCache() { cache.clear(); }
}

// Character with extrinsic state (position, actual char) + flyweight reference
class FormattedChar {
    private final char character;  // extrinsic
    private final int row;         // extrinsic
    private final int col;         // extrinsic
    private final Font font;       // flyweight reference

    public FormattedChar(char character, int row, int col, Font font) {
        this.character = character;
        this.row = row;
        this.col = col;
        this.font = font;
    }

    public String toString() {
        return "'" + character + "' at (" + row + "," + col + ") [" + font.describe() + "]";
    }
}

// ==================== Without Flyweight (for comparison) ====================

class TreeWithoutFlyweight {
    private final int x;
    private final int y;
    private final String name;
    private final String color;
    private final String texture;  // duplicated for every tree!

    public TreeWithoutFlyweight(int x, int y, String name, String color, String texture) {
        this.x = x;
        this.y = y;
        this.name = name;
        this.color = color;
        this.texture = texture;
    }
}

// ==================== Main Demo ====================

public class FlyweightPattern {

    // Simulated texture data (in reality this would be much larger)
    private static final String[] TREE_TYPES = {"Oak", "Pine", "Birch", "Maple", "Willow"};
    private static final String[] COLORS = {"DarkGreen", "LightGreen", "Yellow", "Orange", "Brown"};
    private static final String TEXTURE = "ABCDEFGHIJ".repeat(50); // 500-char simulated texture

    public static void main(String[] args) {
        System.out.println("=== FLYWEIGHT DESIGN PATTERN DEMO ===\n");

        // --- Example 1: Forest ---
        demoForest();

        System.out.println("\n" + "=".repeat(60) + "\n");

        // --- Example 2: Text Editor ---
        demoTextEditor();

        System.out.println("\n" + "=".repeat(60) + "\n");

        // --- Memory Comparison ---
        demoMemoryComparison();
    }

    private static void demoForest() {
        System.out.println("--- Example 1: Forest with 1,000,000 Trees ---\n");

        TreeTypeFactory.clearCache();
        Forest forest = new Forest();
        Random rand = new Random(42);

        long startTime = System.currentTimeMillis();

        for (int i = 0; i < 1_000_000; i++) {
            int x = rand.nextInt(10000);
            int y = rand.nextInt(10000);
            String name = TREE_TYPES[rand.nextInt(TREE_TYPES.length)];
            String color = COLORS[rand.nextInt(COLORS.length)];
            forest.plantTree(x, y, name, color, TEXTURE);
        }

        long elapsed = System.currentTimeMillis() - startTime;

        System.out.println("Trees planted:    " + forest.getTreeCount());
        System.out.println("Unique TreeTypes: " + forest.getUniqueTypes());
        System.out.println("Time taken:       " + elapsed + " ms");

        // Memory estimate WITH flyweight
        // Each Tree: ~24 bytes (x, y, reference)
        // Each TreeType: ~1080 bytes (name + color + 500-char texture)
        long flyweightMem = (long) forest.getTreeCount() * 24 + (long) forest.getUniqueTypes() * 1080;

        // Memory estimate WITHOUT flyweight
        // Each tree stores its own copy: ~1080 + 16 bytes
        long noFlyweightMem = (long) forest.getTreeCount() * 1096;

        System.out.println("\nMemory Estimate (WITH flyweight):    " + formatBytes(flyweightMem));
        System.out.println("Memory Estimate (WITHOUT flyweight): " + formatBytes(noFlyweightMem));
        System.out.println("Memory saved: " + String.format("%.1f%%", (1.0 - (double) flyweightMem / noFlyweightMem) * 100));
    }

    private static void demoTextEditor() {
        System.out.println("--- Example 2: Text Editor Character Formatting ---\n");

        FontFactory.clearCache();
        List<FormattedChar> document = new ArrayList<>();

        String text = "Hello, World! This is a Flyweight Pattern demo.";
        Font normalFont = FontFactory.getFont("Arial", 12, false, false);
        Font boldFont = FontFactory.getFont("Arial", 12, true, false);
        Font italicFont = FontFactory.getFont("Arial", 12, false, true);

        for (int i = 0; i < text.length(); i++) {
            Font font;
            if (i < 5) font = boldFont;        // "Hello" in bold
            else if (i >= 14 && i < 18) font = italicFont; // "This" in italic
            else font = normalFont;

            document.add(new FormattedChar(text.charAt(i), 0, i, font));
        }

        System.out.println("Characters in document: " + document.size());
        System.out.println("Unique Font objects:    " + FontFactory.getCacheSize());
        System.out.println("\nFirst 10 characters:");
        for (int i = 0; i < 10 && i < document.size(); i++) {
            System.out.println("  " + document.get(i));
        }

        System.out.println("\nWithout flyweight: " + document.size() + " Font objects");
        System.out.println("With flyweight:    " + FontFactory.getCacheSize() + " Font objects (shared)");
    }

    private static void demoMemoryComparison() {
        System.out.println("--- Memory Comparison: 1M Trees ---\n");

        // Measure actual heap usage
        System.gc();
        long beforeMem = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();

        TreeTypeFactory.clearCache();
        Forest forest = new Forest();
        Random rand = new Random(123);
        for (int i = 0; i < 1_000_000; i++) {
            forest.plantTree(
                rand.nextInt(10000), rand.nextInt(10000),
                TREE_TYPES[rand.nextInt(TREE_TYPES.length)],
                COLORS[rand.nextInt(COLORS.length)],
                TEXTURE
            );
        }

        long afterMem = Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory();
        long usedWithFlyweight = afterMem - beforeMem;

        System.out.println("Actual heap used (with flyweight):  " + formatBytes(usedWithFlyweight));
        System.out.println("Unique shared flyweights:           " + TreeTypeFactory.getCacheSize());
        System.out.println("\nKey Insight: 1,000,000 trees share only " +
                TreeTypeFactory.getCacheSize() + " TreeType objects!");
        System.out.println("The heavy texture data (500 chars each) is stored ONCE per type,");
        System.out.println("not duplicated across a million tree instances.");
    }

    private static String formatBytes(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return String.format("%.1f KB", bytes / 1024.0);
        return String.format("%.1f MB", bytes / (1024.0 * 1024));
    }
}
