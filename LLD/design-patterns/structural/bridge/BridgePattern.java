/**
 * Bridge Design Pattern
 * 
 * Decouples an abstraction from its implementation so that the two can vary independently.
 * 
 * Example 1: Shape + Color
 * Example 2: Remote + Device
 */

// ============================================================
// EXAMPLE 1: Shape (Abstraction) + Color (Implementor)
// ============================================================

// Implementor interface
interface Color {
    String fill();
    String getColorName();
}

// Concrete Implementors
class Red implements Color {
    public String fill() { return "Filling with RED color"; }
    public String getColorName() { return "Red"; }
}

class Blue implements Color {
    public String fill() { return "Filling with BLUE color"; }
    public String getColorName() { return "Blue"; }
}

class Green implements Color {
    public String fill() { return "Filling with GREEN color"; }
    public String getColorName() { return "Green"; }
}

// Abstraction
abstract class Shape {
    protected Color color;

    public Shape(Color color) {
        this.color = color;
    }

    abstract String draw();

    public String toString() {
        return draw() + " | " + color.fill();
    }
}

// Refined Abstractions
class Circle extends Shape {
    private double radius;

    public Circle(Color color, double radius) {
        super(color);
        this.radius = radius;
    }

    public String draw() {
        return "Drawing Circle (radius=" + radius + ") in " + color.getColorName();
    }
}

class Square extends Shape {
    private double side;

    public Square(Color color, double side) {
        super(color);
        this.side = side;
    }

    public String draw() {
        return "Drawing Square (side=" + side + ") in " + color.getColorName();
    }
}

class Triangle extends Shape {
    private double base, height;

    public Triangle(Color color, double base, double height) {
        super(color);
        this.base = base;
        this.height = height;
    }

    public String draw() {
        return "Drawing Triangle (base=" + base + ", height=" + height + ") in " + color.getColorName();
    }
}

// ============================================================
// EXAMPLE 2: Remote (Abstraction) + Device (Implementor)
// ============================================================

// Implementor interface
interface Device {
    boolean isEnabled();
    void enable();
    void disable();
    int getVolume();
    void setVolume(int volume);
    int getChannel();
    void setChannel(int channel);
    String getName();
}

// Concrete Implementors
class TV implements Device {
    private boolean on = false;
    private int volume = 30;
    private int channel = 1;

    public boolean isEnabled() { return on; }
    public void enable() { on = true; }
    public void disable() { on = false; }
    public int getVolume() { return volume; }
    public void setVolume(int volume) { this.volume = Math.max(0, Math.min(100, volume)); }
    public int getChannel() { return channel; }
    public void setChannel(int channel) { this.channel = channel; }
    public String getName() { return "TV"; }
}

class Radio implements Device {
    private boolean on = false;
    private int volume = 20;
    private int channel = 88;

    public boolean isEnabled() { return on; }
    public void enable() { on = true; }
    public void disable() { on = false; }
    public int getVolume() { return volume; }
    public void setVolume(int volume) { this.volume = Math.max(0, Math.min(100, volume)); }
    public int getChannel() { return channel; }
    public void setChannel(int channel) { this.channel = channel; }
    public String getName() { return "Radio"; }
}

// Abstraction
class Remote {
    protected Device device;

    public Remote(Device device) {
        this.device = device;
    }

    public void togglePower() {
        if (device.isEnabled()) {
            device.disable();
            System.out.println("  " + device.getName() + " turned OFF");
        } else {
            device.enable();
            System.out.println("  " + device.getName() + " turned ON");
        }
    }

    public void volumeUp() {
        device.setVolume(device.getVolume() + 10);
        System.out.println("  " + device.getName() + " volume: " + device.getVolume());
    }

    public void volumeDown() {
        device.setVolume(device.getVolume() - 10);
        System.out.println("  " + device.getName() + " volume: " + device.getVolume());
    }

    public void channelUp() {
        device.setChannel(device.getChannel() + 1);
        System.out.println("  " + device.getName() + " channel: " + device.getChannel());
    }
}

// Refined Abstraction
class AdvancedRemote extends Remote {
    public AdvancedRemote(Device device) {
        super(device);
    }

    public void mute() {
        device.setVolume(0);
        System.out.println("  " + device.getName() + " MUTED");
    }

    public void setChannel(int channel) {
        device.setChannel(channel);
        System.out.println("  " + device.getName() + " jumped to channel: " + channel);
    }
}

// ============================================================
// MAIN
// ============================================================

public class BridgePattern {
    public static void main(String[] args) {
        System.out.println("=== BRIDGE PATTERN DEMO ===\n");

        // Example 1: Shapes with Colors
        System.out.println("--- Example 1: Shape + Color ---");
        Shape[] shapes = {
            new Circle(new Red(), 5),
            new Circle(new Blue(), 3),
            new Square(new Green(), 4),
            new Triangle(new Red(), 6, 3),
            new Square(new Blue(), 7)
        };

        for (Shape shape : shapes) {
            System.out.println("  " + shape);
        }

        // Example 2: Remote + Device
        System.out.println("\n--- Example 2: Remote + Device ---");

        System.out.println("\nBasic Remote with TV:");
        Remote tvRemote = new Remote(new TV());
        tvRemote.togglePower();
        tvRemote.volumeUp();
        tvRemote.channelUp();

        System.out.println("\nAdvanced Remote with Radio:");
        AdvancedRemote radioRemote = new AdvancedRemote(new Radio());
        radioRemote.togglePower();
        radioRemote.volumeUp();
        radioRemote.volumeUp();
        radioRemote.mute();
        radioRemote.setChannel(101);

        System.out.println("\nAdvanced Remote with TV:");
        AdvancedRemote advTv = new AdvancedRemote(new TV());
        advTv.togglePower();
        advTv.setChannel(42);
        advTv.volumeDown();

        System.out.println("\n=== Key Insight ===");
        System.out.println("Shapes and Colors vary independently - no ShapeColor explosion!");
        System.out.println("Remotes and Devices vary independently - any remote works with any device!");
    }
}
