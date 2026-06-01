import java.util.ArrayList;
import java.util.List;

// ============================================================
// COMPOSITE DESIGN PATTERN
// ============================================================

// --- Example 1: File System ---

interface FileSystemComponent {
    String getName();
    long getSize();
    void display(String indent);
}

class File implements FileSystemComponent {
    private final String name;
    private final long size;

    public File(String name, long size) {
        this.name = name;
        this.size = size;
    }

    @Override
    public String getName() { return name; }

    @Override
    public long getSize() { return size; }

    @Override
    public void display(String indent) {
        System.out.println(indent + "📄 " + name + " (" + size + " KB)");
    }
}

class Directory implements FileSystemComponent {
    private final String name;
    private final List<FileSystemComponent> children = new ArrayList<>();

    public Directory(String name) {
        this.name = name;
    }

    public void add(FileSystemComponent component) {
        children.add(component);
    }

    public void remove(FileSystemComponent component) {
        children.remove(component);
    }

    public List<FileSystemComponent> getChildren() {
        return children;
    }

    @Override
    public String getName() { return name; }

    @Override
    public long getSize() {
        long total = 0;
        for (FileSystemComponent child : children) {
            total += child.getSize();
        }
        return total;
    }

    @Override
    public void display(String indent) {
        System.out.println(indent + "📁 " + name + " (" + getSize() + " KB)");
        for (FileSystemComponent child : children) {
            child.display(indent + "  ");
        }
    }
}

// --- Example 2: Organization Hierarchy ---

interface OrgComponent {
    String getName();
    double getSalary();
    void display(String indent);
}

class Employee implements OrgComponent {
    private final String name;
    private final String role;
    private final double salary;

    public Employee(String name, String role, double salary) {
        this.name = name;
        this.role = role;
        this.salary = salary;
    }

    @Override
    public String getName() { return name; }

    @Override
    public double getSalary() { return salary; }

    @Override
    public void display(String indent) {
        System.out.println(indent + "👤 " + name + " [" + role + "] - $" + salary);
    }
}

class Department implements OrgComponent {
    private final String name;
    private final List<OrgComponent> members = new ArrayList<>();

    public Department(String name) {
        this.name = name;
    }

    public void add(OrgComponent component) {
        members.add(component);
    }

    public void remove(OrgComponent component) {
        members.remove(component);
    }

    @Override
    public String getName() { return name; }

    @Override
    public double getSalary() {
        double total = 0;
        for (OrgComponent member : members) {
            total += member.getSalary();
        }
        return total;
    }

    @Override
    public void display(String indent) {
        System.out.println(indent + "🏢 " + name + " (Total: $" + getSalary() + ")");
        for (OrgComponent member : members) {
            member.display(indent + "  ");
        }
    }
}

// --- Main Demo ---

public class CompositePattern {
    public static void main(String[] args) {
        System.out.println("=== COMPOSITE PATTERN: File System Example ===\n");

        Directory root = new Directory("root");
        Directory src = new Directory("src");
        Directory docs = new Directory("docs");

        src.add(new File("Main.java", 15));
        src.add(new File("Utils.java", 8));

        Directory tests = new Directory("tests");
        tests.add(new File("MainTest.java", 10));
        src.add(tests);

        docs.add(new File("README.md", 3));
        docs.add(new File("API.md", 5));

        root.add(src);
        root.add(docs);
        root.add(new File(".gitignore", 1));

        root.display("");

        System.out.println("\nTotal size of root: " + root.getSize() + " KB");
        System.out.println("Total size of src: " + src.getSize() + " KB");

        // Demonstrate removal
        System.out.println("\n--- After removing API.md from docs ---");
        docs.remove(docs.getChildren().get(1));
        root.display("");

        System.out.println("\n\n=== COMPOSITE PATTERN: Organization Hierarchy ===\n");

        Department company = new Department("TechCorp");

        Department engineering = new Department("Engineering");
        engineering.add(new Employee("Alice", "Senior Dev", 120000));
        engineering.add(new Employee("Bob", "Junior Dev", 80000));

        Department devOps = new Department("DevOps");
        devOps.add(new Employee("Charlie", "SRE", 110000));
        engineering.add(devOps);

        Department marketing = new Department("Marketing");
        marketing.add(new Employee("Diana", "Marketing Lead", 100000));
        marketing.add(new Employee("Eve", "Content Writer", 70000));

        company.add(engineering);
        company.add(marketing);
        company.add(new Employee("Frank", "CEO", 200000));

        company.display("");

        System.out.println("\nTotal salary budget: $" + company.getSalary());
        System.out.println("Engineering budget: $" + engineering.getSalary());
    }
}
