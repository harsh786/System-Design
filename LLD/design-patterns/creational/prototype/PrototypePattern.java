import java.util.HashMap;
import java.util.Map;
import java.util.ArrayList;
import java.util.List;

// ============================================================
// PROTOTYPE DESIGN PATTERN
// ============================================================

// --- Prototype Interface ---
interface Shape extends Cloneable {
    Shape clone();
    void draw();
    String getType();
}

// --- Concrete Prototype: Circle ---
class Circle implements Shape {
    private int radius;
    private String color;
    private int[] center; // Reference type to demonstrate deep vs shallow copy

    public Circle(int radius, String color, int x, int y) {
        this.radius = radius;
        this.color = color;
        this.center = new int[]{x, y};
    }

    // Deep copy
    @Override
    public Shape clone() {
        Circle copy = new Circle(this.radius, this.color, this.center[0], this.center[1]);
        return copy;
    }

    @Override
    public void draw() {
        System.out.printf("  Circle [radius=%d, color=%s, center=(%d,%d)]%n",
                radius, color, center[0], center[1]);
    }

    @Override
    public String getType() { return "Circle"; }

    public void setCenter(int x, int y) { center[0] = x; center[1] = y; }
    public int[] getCenter() { return center; }
    public void setColor(String color) { this.color = color; }
}

// --- Concrete Prototype: Rectangle ---
class Rectangle implements Shape {
    private int width, height;
    private String color;

    public Rectangle(int width, int height, String color) {
        this.width = width;
        this.height = height;
        this.color = color;
    }

    @Override
    public Shape clone() {
        return new Rectangle(this.width, this.height, this.color);
    }

    @Override
    public void draw() {
        System.out.printf("  Rectangle [%dx%d, color=%s]%n", width, height, color);
    }

    @Override
    public String getType() { return "Rectangle"; }

    public void setColor(String color) { this.color = color; }
}

// --- Concrete Prototype: ComplexShape (expensive to create) ---
class ComplexShape implements Shape {
    private String name;
    private List<int[]> points; // Simulates complex internal state

    public ComplexShape(String name) {
        this.name = name;
        this.points = new ArrayList<>();
        // Simulate expensive computation
        System.out.println("  [EXPENSIVE] Creating ComplexShape: " + name);
        try { Thread.sleep(100); } catch (InterruptedException e) {}
        for (int i = 0; i < 5; i++) {
            points.add(new int[]{i * 10, i * 20});
        }
    }

    // Private constructor for cloning (skips expensive init)
    private ComplexShape(String name, List<int[]> points) {
        this.name = name;
        this.points = new ArrayList<>();
        for (int[] p : points) {
            this.points.add(new int[]{p[0], p[1]}); // Deep copy each point
        }
    }

    @Override
    public Shape clone() {
        return new ComplexShape(this.name, this.points);
    }

    @Override
    public void draw() {
        System.out.printf("  ComplexShape [name=%s, points=%d]%n", name, points.size());
    }

    @Override
    public String getType() { return "ComplexShape"; }

    public void setName(String name) { this.name = name; }
}

// --- Prototype Registry / Cache ---
class ShapeRegistry {
    private Map<String, Shape> cache = new HashMap<>();

    public void loadDefaults() {
        cache.put("small-circle", new Circle(5, "red", 0, 0));
        cache.put("big-circle", new Circle(20, "blue", 100, 100));
        cache.put("standard-rect", new Rectangle(10, 5, "green"));
        cache.put("complex-star", new ComplexShape("Star"));
    }

    public void register(String key, Shape shape) {
        cache.put(key, shape);
    }

    public Shape get(String key) {
        Shape cached = cache.get(key);
        if (cached == null) {
            throw new IllegalArgumentException("No prototype: " + key);
        }
        return cached.clone(); // Return a clone, never the original
    }
}

// ============================================================
// REAL-WORLD EXAMPLE: Game Character Cloning
// ============================================================

interface GameCharacter {
    GameCharacter clone();
    void display();
}

class Warrior implements GameCharacter {
    private String name;
    private int hp, attack, defense;
    private List<String> inventory;

    public Warrior(String name, int hp, int attack, int defense, List<String> inventory) {
        this.name = name;
        this.hp = hp;
        this.attack = attack;
        this.defense = defense;
        this.inventory = new ArrayList<>(inventory);
    }

    @Override
    public GameCharacter clone() {
        return new Warrior(this.name, this.hp, this.attack, this.defense, this.inventory);
    }

    @Override
    public void display() {
        System.out.printf("  Warrior[%s] HP=%d ATK=%d DEF=%d items=%s%n",
                name, hp, attack, defense, inventory);
    }

    public void setName(String name) { this.name = name; }
    public void addItem(String item) { this.inventory.add(item); }
}

// ============================================================
// DEEP COPY vs SHALLOW COPY Demonstration
// ============================================================

class ShallowCircle implements Shape {
    private int radius;
    private int[] center; // Shared reference in shallow copy!

    public ShallowCircle(int radius, int x, int y) {
        this.radius = radius;
        this.center = new int[]{x, y};
    }

    // SHALLOW copy - shares the center array!
    @Override
    public Shape clone() {
        ShallowCircle copy = new ShallowCircle(this.radius, 0, 0);
        copy.center = this.center; // Same reference!
        return copy;
    }

    @Override
    public void draw() {
        System.out.printf("  ShallowCircle [radius=%d, center=(%d,%d)]%n",
                radius, center[0], center[1]);
    }

    @Override
    public String getType() { return "ShallowCircle"; }

    public void setCenter(int x, int y) { center[0] = x; center[1] = y; }
}

// ============================================================
// MAIN
// ============================================================

public class PrototypePattern {
    public static void main(String[] args) {
        System.out.println("=== PROTOTYPE DESIGN PATTERN ===\n");

        // --- 1. Registry Demo ---
        System.out.println("1. PROTOTYPE REGISTRY");
        System.out.println("   Loading prototypes (expensive objects created once)...");
        ShapeRegistry registry = new ShapeRegistry();
        registry.loadDefaults();

        System.out.println("\n   Cloning from registry (cheap):");
        Shape c1 = registry.get("small-circle");
        Shape c2 = registry.get("small-circle");
        Shape r1 = registry.get("standard-rect");
        Shape star = registry.get("complex-star"); // No expensive init!
        c1.draw();
        c2.draw();
        r1.draw();
        star.draw();

        // --- 2. Deep Copy vs Shallow Copy ---
        System.out.println("\n2. DEEP COPY vs SHALLOW COPY");

        System.out.println("   Deep copy (Circle):");
        Circle original = new Circle(10, "red", 50, 50);
        Circle deepClone = (Circle) original.clone();
        deepClone.setCenter(999, 999);
        System.out.print("   Original: "); original.draw();
        System.out.print("   Clone:    "); deepClone.draw();
        System.out.println("   -> Original NOT affected (deep copy works correctly)");

        System.out.println("\n   Shallow copy (ShallowCircle):");
        ShallowCircle origShallow = new ShallowCircle(10, 50, 50);
        ShallowCircle shallowClone = (ShallowCircle) origShallow.clone();
        shallowClone.setCenter(999, 999);
        System.out.print("   Original: "); origShallow.draw();
        System.out.print("   Clone:    "); shallowClone.draw();
        System.out.println("   -> Original IS affected (shallow copy shares reference!)");

        // --- 3. Game Character Cloning ---
        System.out.println("\n3. GAME CHARACTER CLONING");
        List<String> baseItems = new ArrayList<>();
        baseItems.add("Sword");
        baseItems.add("Shield");
        Warrior template = new Warrior("BaseWarrior", 100, 25, 15, baseItems);

        Warrior w1 = (Warrior) template.clone();
        w1.setName("Aragorn");
        w1.addItem("Anduril");

        Warrior w2 = (Warrior) template.clone();
        w2.setName("Boromir");
        w2.addItem("Horn of Gondor");

        System.out.println("   Template:");
        template.display();
        System.out.println("   Clones (independent copies):");
        w1.display();
        w2.display();

        // --- 4. Performance benefit ---
        System.out.println("\n4. PERFORMANCE: Cloning vs Creating ComplexShape");
        long start = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) new ComplexShape("obj" + i);
        long createTime = System.currentTimeMillis() - start;

        ComplexShape proto = new ComplexShape("prototype");
        start = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) proto.clone();
        long cloneTime = System.currentTimeMillis() - start;

        System.out.printf("   Creating 5 objects: %dms%n", createTime);
        System.out.printf("   Cloning 5 objects:  %dms%n", cloneTime);
        System.out.println("   -> Cloning avoids expensive initialization!\n");
    }
}
