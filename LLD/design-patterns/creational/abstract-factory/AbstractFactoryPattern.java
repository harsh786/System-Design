/**
 * Abstract Factory Design Pattern
 * Real-world example: Cross-platform UI toolkit
 *
 * Creates families of related objects (Button, TextField, Checkbox)
 * without specifying their concrete classes.
 */

// ==================== Abstract Products ====================

interface Button {
    void render();
    void onClick(String action);
}

interface TextField {
    void render();
    String getValue();
    void setValue(String text);
}

interface Checkbox {
    void render();
    boolean isChecked();
    void setChecked(boolean checked);
}

// ==================== Windows Concrete Products ====================

class WindowsButton implements Button {
    @Override
    public void render() {
        System.out.println("[Windows Button] Rendering flat-style button with sharp corners");
    }

    @Override
    public void onClick(String action) {
        System.out.println("[Windows Button] Click handled: " + action);
    }
}

class WindowsTextField implements TextField {
    private String value = "";

    @Override
    public void render() {
        System.out.println("[Windows TextField] Rendering text field with Windows theme");
    }

    @Override
    public String getValue() {
        return value;
    }

    @Override
    public void setValue(String text) {
        this.value = text;
        System.out.println("[Windows TextField] Value set to: " + text);
    }
}

class WindowsCheckbox implements Checkbox {
    private boolean checked = false;

    @Override
    public void render() {
        System.out.println("[Windows Checkbox] Rendering square checkbox with checkmark");
    }

    @Override
    public boolean isChecked() {
        return checked;
    }

    @Override
    public void setChecked(boolean checked) {
        this.checked = checked;
        System.out.println("[Windows Checkbox] State: " + (checked ? "checked" : "unchecked"));
    }
}

// ==================== Mac Concrete Products ====================

class MacButton implements Button {
    @Override
    public void render() {
        System.out.println("[Mac Button] Rendering rounded aqua-style button");
    }

    @Override
    public void onClick(String action) {
        System.out.println("[Mac Button] Click handled: " + action);
    }
}

class MacTextField implements TextField {
    private String value = "";

    @Override
    public void render() {
        System.out.println("[Mac TextField] Rendering text field with macOS theme");
    }

    @Override
    public String getValue() {
        return value;
    }

    @Override
    public void setValue(String text) {
        this.value = text;
        System.out.println("[Mac TextField] Value set to: " + text);
    }
}

class MacCheckbox implements Checkbox {
    private boolean checked = false;

    @Override
    public void render() {
        System.out.println("[Mac Checkbox] Rendering rounded checkbox with blue tint");
    }

    @Override
    public boolean isChecked() {
        return checked;
    }

    @Override
    public void setChecked(boolean checked) {
        this.checked = checked;
        System.out.println("[Mac Checkbox] State: " + (checked ? "checked" : "unchecked"));
    }
}

// ==================== Abstract Factory ====================

interface UIFactory {
    Button createButton();
    TextField createTextField();
    Checkbox createCheckbox();
}

// ==================== Concrete Factories ====================

class WindowsUIFactory implements UIFactory {
    @Override
    public Button createButton() {
        return new WindowsButton();
    }

    @Override
    public TextField createTextField() {
        return new WindowsTextField();
    }

    @Override
    public Checkbox createCheckbox() {
        return new WindowsCheckbox();
    }
}

class MacUIFactory implements UIFactory {
    @Override
    public Button createButton() {
        return new MacButton();
    }

    @Override
    public TextField createTextField() {
        return new MacTextField();
    }

    @Override
    public Checkbox createCheckbox() {
        return new MacCheckbox();
    }
}

// ==================== Client Code ====================

class Application {
    private final Button button;
    private final TextField textField;
    private final Checkbox checkbox;

    public Application(UIFactory factory) {
        // Client works only with abstract interfaces
        this.button = factory.createButton();
        this.textField = factory.createTextField();
        this.checkbox = factory.createCheckbox();
    }

    public void renderUI() {
        System.out.println("--- Rendering Application UI ---");
        button.render();
        textField.render();
        checkbox.render();
    }

    public void interact() {
        System.out.println("\n--- User Interaction ---");
        textField.setValue("Hello, World!");
        checkbox.setChecked(true);
        button.onClick("Submit Form");
    }
}

// ==================== Demo ====================

public class AbstractFactoryPattern {

    // Factory selection based on runtime configuration
    private static UIFactory getFactory(String os) {
        switch (os.toLowerCase()) {
            case "windows":
                return new WindowsUIFactory();
            case "mac":
                return new MacUIFactory();
            default:
                throw new IllegalArgumentException("Unknown OS: " + os);
        }
    }

    public static void main(String[] args) {
        System.out.println("========== Abstract Factory Pattern Demo ==========\n");

        // Simulate Windows environment
        System.out.println(">> Platform: Windows");
        UIFactory windowsFactory = getFactory("windows");
        Application windowsApp = new Application(windowsFactory);
        windowsApp.renderUI();
        windowsApp.interact();

        System.out.println("\n");

        // Simulate Mac environment
        System.out.println(">> Platform: Mac");
        UIFactory macFactory = getFactory("mac");
        Application macApp = new Application(macFactory);
        macApp.renderUI();
        macApp.interact();

        System.out.println("\n========== End Demo ==========");
    }
}
