import java.util.*;

// ==================== COMMAND INTERFACE ====================
interface Command {
    void execute();
    void undo();
    String getDescription();
}

// ==================== NO-OP COMMAND ====================
class NoCommand implements Command {
    public void execute() {}
    public void undo() {}
    public String getDescription() { return "No Command"; }
}

// ==================== RECEIVERS ====================
class Light {
    private String location;
    private boolean on;
    private int brightness; // 0-100

    public Light(String location) {
        this.location = location;
        this.on = false;
        this.brightness = 100;
    }

    public void on() { on = true; System.out.println(location + " Light is ON (brightness: " + brightness + "%)"); }
    public void off() { on = false; System.out.println(location + " Light is OFF"); }
    public boolean isOn() { return on; }
    public int getBrightness() { return brightness; }
    public void setBrightness(int level) { brightness = level; System.out.println(location + " Light brightness set to " + level + "%"); }
}

class Fan {
    public static final int OFF = 0, LOW = 1, MEDIUM = 2, HIGH = 3;
    private String location;
    private int speed;

    public Fan(String location) { this.location = location; this.speed = OFF; }

    public void setSpeed(int speed) {
        this.speed = speed;
        String[] labels = {"OFF", "LOW", "MEDIUM", "HIGH"};
        System.out.println(location + " Fan speed set to " + labels[speed]);
    }

    public int getSpeed() { return speed; }
}

class Thermostat {
    private String location;
    private int temperature;

    public Thermostat(String location) { this.location = location; this.temperature = 20; }

    public void setTemperature(int temp) {
        this.temperature = temp;
        System.out.println(location + " Thermostat set to " + temp + "°C");
    }

    public int getTemperature() { return temperature; }
}

// ==================== CONCRETE COMMANDS ====================
class LightOnCommand implements Command {
    private Light light;

    public LightOnCommand(Light light) { this.light = light; }
    public void execute() { light.on(); }
    public void undo() { light.off(); }
    public String getDescription() { return "Light ON"; }
}

class LightOffCommand implements Command {
    private Light light;

    public LightOffCommand(Light light) { this.light = light; }
    public void execute() { light.off(); }
    public void undo() { light.on(); }
    public String getDescription() { return "Light OFF"; }
}

class FanSpeedCommand implements Command {
    private Fan fan;
    private int newSpeed;
    private int previousSpeed;

    public FanSpeedCommand(Fan fan, int speed) { this.fan = fan; this.newSpeed = speed; }
    public void execute() { previousSpeed = fan.getSpeed(); fan.setSpeed(newSpeed); }
    public void undo() { fan.setSpeed(previousSpeed); }
    public String getDescription() { return "Fan Speed -> " + newSpeed; }
}

class ThermostatCommand implements Command {
    private Thermostat thermostat;
    private int newTemp;
    private int previousTemp;

    public ThermostatCommand(Thermostat thermostat, int temp) { this.thermostat = thermostat; this.newTemp = temp; }
    public void execute() { previousTemp = thermostat.getTemperature(); thermostat.setTemperature(newTemp); }
    public void undo() { thermostat.setTemperature(previousTemp); }
    public String getDescription() { return "Thermostat -> " + newTemp + "°C"; }
}

// ==================== MACRO COMMAND ====================
class MacroCommand implements Command {
    private Command[] commands;
    private String name;

    public MacroCommand(String name, Command[] commands) { this.name = name; this.commands = commands; }

    public void execute() {
        System.out.println("--- Executing Macro: " + name + " ---");
        for (Command cmd : commands) cmd.execute();
    }

    public void undo() {
        System.out.println("--- Undoing Macro: " + name + " ---");
        for (int i = commands.length - 1; i >= 0; i--) commands[i].undo();
    }

    public String getDescription() { return "Macro: " + name; }
}

// ==================== INVOKER: REMOTE CONTROL ====================
class RemoteControl {
    private Command[] onCommands;
    private Command[] offCommands;
    private Deque<Command> history;

    public RemoteControl(int slots) {
        onCommands = new Command[slots];
        offCommands = new Command[slots];
        history = new ArrayDeque<>();
        Command noCmd = new NoCommand();
        Arrays.fill(onCommands, noCmd);
        Arrays.fill(offCommands, noCmd);
    }

    public void setCommand(int slot, Command onCmd, Command offCmd) {
        onCommands[slot] = onCmd;
        offCommands[slot] = offCmd;
    }

    public void pressOn(int slot) {
        System.out.println("[Slot " + slot + " ON pressed]");
        onCommands[slot].execute();
        history.push(onCommands[slot]);
    }

    public void pressOff(int slot) {
        System.out.println("[Slot " + slot + " OFF pressed]");
        offCommands[slot].execute();
        history.push(offCommands[slot]);
    }

    public void pressUndo() {
        if (!history.isEmpty()) {
            Command lastCmd = history.pop();
            System.out.println("[UNDO: " + lastCmd.getDescription() + "]");
            lastCmd.undo();
        } else {
            System.out.println("[Nothing to undo]");
        }
    }

    public void printHistory() {
        System.out.println("\n--- Command History (most recent first) ---");
        for (Command cmd : history) System.out.println("  " + cmd.getDescription());
        System.out.println();
    }
}

// ==================== TEXT EDITOR EXAMPLE ====================
class TextEditor {
    private StringBuilder content = new StringBuilder();
    private boolean bold = false;

    public void insert(int pos, String text) { content.insert(pos, text); }
    public void delete(int pos, int length) { content.delete(pos, pos + length); }
    public String substring(int pos, int length) { return content.substring(pos, pos + length); }
    public void setBold(boolean b) { bold = b; }
    public boolean isBold() { return bold; }
    public int length() { return content.length(); }
    public String getContent() { return content.toString(); }
}

class TypeCommand implements Command {
    private TextEditor editor;
    private String text;
    private int position;

    public TypeCommand(TextEditor editor, String text, int position) {
        this.editor = editor; this.text = text; this.position = position;
    }

    public void execute() { editor.insert(position, text); }
    public void undo() { editor.delete(position, text.length()); }
    public String getDescription() { return "Type '" + text + "' at " + position; }
}

class DeleteCommand implements Command {
    private TextEditor editor;
    private int position;
    private int length;
    private String deletedText;

    public DeleteCommand(TextEditor editor, int position, int length) {
        this.editor = editor; this.position = position; this.length = length;
    }

    public void execute() { deletedText = editor.substring(position, length); editor.delete(position, length); }
    public void undo() { editor.insert(position, deletedText); }
    public String getDescription() { return "Delete " + length + " chars at " + position; }
}

class BoldCommand implements Command {
    private TextEditor editor;
    private boolean previousState;

    public BoldCommand(TextEditor editor) { this.editor = editor; }
    public void execute() { previousState = editor.isBold(); editor.setBold(!previousState); }
    public void undo() { editor.setBold(previousState); }
    public String getDescription() { return "Toggle Bold"; }
}

class EditorCommandManager {
    private Deque<Command> undoStack = new ArrayDeque<>();
    private Deque<Command> redoStack = new ArrayDeque<>();

    public void executeCommand(Command cmd) {
        cmd.execute();
        undoStack.push(cmd);
        redoStack.clear();
    }

    public void undo() {
        if (!undoStack.isEmpty()) {
            Command cmd = undoStack.pop();
            System.out.println("  [Undo: " + cmd.getDescription() + "]");
            cmd.undo();
            redoStack.push(cmd);
        }
    }

    public void redo() {
        if (!redoStack.isEmpty()) {
            Command cmd = redoStack.pop();
            System.out.println("  [Redo: " + cmd.getDescription() + "]");
            cmd.execute();
            undoStack.push(cmd);
        }
    }
}

// ==================== MAIN ====================
public class CommandPattern {
    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════╗");
        System.out.println("║     COMMAND PATTERN DEMONSTRATION        ║");
        System.out.println("╚══════════════════════════════════════════╝\n");

        // --- Remote Control Example ---
        System.out.println("========== REMOTE CONTROL EXAMPLE ==========\n");

        Light livingRoom = new Light("Living Room");
        Light kitchen = new Light("Kitchen");
        Fan ceilingFan = new Fan("Living Room");
        Thermostat thermostat = new Thermostat("Home");

        RemoteControl remote = new RemoteControl(4);
        remote.setCommand(0, new LightOnCommand(livingRoom), new LightOffCommand(livingRoom));
        remote.setCommand(1, new LightOnCommand(kitchen), new LightOffCommand(kitchen));
        remote.setCommand(2, new FanSpeedCommand(ceilingFan, Fan.HIGH), new FanSpeedCommand(ceilingFan, Fan.OFF));
        remote.setCommand(3, new ThermostatCommand(thermostat, 25), new ThermostatCommand(thermostat, 20));

        remote.pressOn(0);
        remote.pressOn(2);
        remote.pressOn(3);
        remote.pressOff(0);

        System.out.println("\n--- Undo Demo ---");
        remote.pressUndo(); // undo light off -> light on
        remote.pressUndo(); // undo thermostat 25 -> 20

        remote.printHistory();

        // --- Macro Command ---
        System.out.println("========== MACRO COMMAND EXAMPLE ==========\n");

        Command[] partyOn = {
            new LightOnCommand(livingRoom),
            new FanSpeedCommand(ceilingFan, Fan.HIGH),
            new ThermostatCommand(thermostat, 22)
        };
        MacroCommand partyMacro = new MacroCommand("Party Mode", partyOn);
        partyMacro.execute();
        System.out.println("\n--- Undoing Party Mode ---");
        partyMacro.undo();

        // --- Text Editor Example ---
        System.out.println("\n========== TEXT EDITOR EXAMPLE ==========\n");

        TextEditor editor = new TextEditor();
        EditorCommandManager mgr = new EditorCommandManager();

        mgr.executeCommand(new TypeCommand(editor, "Hello", 0));
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.executeCommand(new TypeCommand(editor, " World", 5));
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.executeCommand(new TypeCommand(editor, "!", 11));
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.executeCommand(new DeleteCommand(editor, 5, 6));
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.executeCommand(new BoldCommand(editor));
        System.out.println("  Bold: " + editor.isBold());

        System.out.println("\n--- Undo/Redo Demo ---");
        mgr.undo(); // undo bold
        System.out.println("  Bold: " + editor.isBold());

        mgr.undo(); // undo delete
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.undo(); // undo "!"
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        System.out.println("\n--- Redo ---");
        mgr.redo(); // redo "!"
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        mgr.redo(); // redo delete
        System.out.println("  Content: \"" + editor.getContent() + "\"");

        System.out.println("\n✓ Command Pattern demonstration complete.");
    }
}
