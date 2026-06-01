import java.util.*;

public class MementoPattern {

    // ==================== Example 1: Text Editor ====================

    // Memento - immutable snapshot of editor state
    static class EditorMemento {
        private final String content;
        private final int cursorPosition;
        private final int fontSize;
        private final long timestamp;

        EditorMemento(String content, int cursorPosition, int fontSize) {
            this.content = content;
            this.cursorPosition = cursorPosition;
            this.fontSize = fontSize;
            this.timestamp = System.currentTimeMillis();
        }

        String getContent() { return content; }
        int getCursorPosition() { return cursorPosition; }
        int getFontSize() { return fontSize; }
        long getTimestamp() { return timestamp; }

        @Override
        public String toString() {
            return String.format("[content=\"%s\", cursor=%d, fontSize=%d]",
                content, cursorPosition, fontSize);
        }
    }

    // Originator - the object whose state we want to save/restore
    static class TextEditor {
        private String content;
        private int cursorPosition;
        private int fontSize;

        public TextEditor() {
            this.content = "";
            this.cursorPosition = 0;
            this.fontSize = 12;
        }

        public void type(String text) {
            content = content.substring(0, cursorPosition) + text + content.substring(cursorPosition);
            cursorPosition += text.length();
        }

        public void moveCursor(int position) {
            this.cursorPosition = Math.max(0, Math.min(position, content.length()));
        }

        public void setFontSize(int size) {
            this.fontSize = size;
        }

        public EditorMemento save() {
            return new EditorMemento(content, cursorPosition, fontSize);
        }

        public void restore(EditorMemento memento) {
            this.content = memento.getContent();
            this.cursorPosition = memento.getCursorPosition();
            this.fontSize = memento.getFontSize();
        }

        @Override
        public String toString() {
            return String.format("TextEditor{content=\"%s\", cursor=%d, fontSize=%d}",
                content, cursorPosition, fontSize);
        }
    }

    // Caretaker - manages history of mementos with undo/redo
    static class History {
        private final Deque<EditorMemento> undoStack = new ArrayDeque<>();
        private final Deque<EditorMemento> redoStack = new ArrayDeque<>();
        private final int maxSize;

        public History(int maxSize) {
            this.maxSize = maxSize;
        }

        public void save(EditorMemento memento) {
            if (undoStack.size() >= maxSize) {
                // Remove oldest to prevent memory issues
                ((ArrayDeque<EditorMemento>) undoStack).removeLast();
            }
            undoStack.push(memento);
            redoStack.clear(); // new save invalidates redo history
        }

        public EditorMemento undo() {
            if (undoStack.isEmpty()) {
                System.out.println("  Nothing to undo!");
                return null;
            }
            EditorMemento memento = undoStack.pop();
            redoStack.push(memento);
            return undoStack.isEmpty() ? null : undoStack.peek();
        }

        public EditorMemento redo() {
            if (redoStack.isEmpty()) {
                System.out.println("  Nothing to redo!");
                return null;
            }
            EditorMemento memento = redoStack.pop();
            undoStack.push(memento);
            return memento;
        }

        public int size() { return undoStack.size(); }
    }

    // ==================== Example 2: Game Save System ====================

    static class GameMemento {
        private final int x, y;
        private final int health;
        private final List<String> inventory;

        GameMemento(int x, int y, int health, List<String> inventory) {
            this.x = x;
            this.y = y;
            this.health = health;
            this.inventory = Collections.unmodifiableList(new ArrayList<>(inventory));
        }

        int getX() { return x; }
        int getY() { return y; }
        int getHealth() { return health; }
        List<String> getInventory() { return inventory; }
    }

    static class GameCharacter {
        private int x, y;
        private int health;
        private List<String> inventory;

        public GameCharacter(String name) {
            this.x = 0;
            this.y = 0;
            this.health = 100;
            this.inventory = new ArrayList<>();
        }

        public void move(int dx, int dy) { x += dx; y += dy; }
        public void takeDamage(int dmg) { health = Math.max(0, health - dmg); }
        public void pickUp(String item) { inventory.add(item); }

        public GameMemento saveGame() {
            return new GameMemento(x, y, health, inventory);
        }

        public void loadGame(GameMemento memento) {
            this.x = memento.getX();
            this.y = memento.getY();
            this.health = memento.getHealth();
            this.inventory = new ArrayList<>(memento.getInventory());
        }

        @Override
        public String toString() {
            return String.format("Character{pos=(%d,%d), health=%d, inventory=%s}",
                x, y, health, inventory);
        }
    }

    static class GameSaveManager {
        private final List<GameMemento> saves = new ArrayList<>();
        private final int maxSlots;

        public GameSaveManager(int maxSlots) {
            this.maxSlots = maxSlots;
        }

        public void save(GameMemento memento) {
            if (saves.size() >= maxSlots) {
                saves.remove(0); // remove oldest
                System.out.println("  (Oldest save removed - max " + maxSlots + " slots)");
            }
            saves.add(memento);
        }

        public GameMemento load(int slot) {
            if (slot < 0 || slot >= saves.size()) return null;
            return saves.get(slot);
        }

        public int getSaveCount() { return saves.size(); }
    }

    // ==================== Main ====================

    public static void main(String[] args) {
        System.out.println("=== MEMENTO PATTERN DEMO ===\n");

        // --- Text Editor Example ---
        System.out.println("--- Text Editor with Undo/Redo ---");
        TextEditor editor = new TextEditor();
        History history = new History(5); // max 5 states

        // Initial state
        history.save(editor.save());
        editor.type("Hello");
        System.out.println("After typing 'Hello': " + editor);
        history.save(editor.save());

        editor.type(" World");
        System.out.println("After typing ' World': " + editor);
        history.save(editor.save());

        editor.setFontSize(16);
        editor.type("!");
        System.out.println("After '!' + fontSize=16: " + editor);
        history.save(editor.save());

        // Undo
        System.out.println("\n  [Undo]");
        EditorMemento prev = history.undo();
        if (prev != null) editor.restore(prev);
        System.out.println("After undo: " + editor);

        System.out.println("  [Undo]");
        prev = history.undo();
        if (prev != null) editor.restore(prev);
        System.out.println("After undo: " + editor);

        // Redo
        System.out.println("  [Redo]");
        EditorMemento next = history.redo();
        if (next != null) editor.restore(next);
        System.out.println("After redo: " + editor);

        // --- Game Save Example ---
        System.out.println("\n--- Game Save System ---");
        GameCharacter hero = new GameCharacter("Hero");
        GameSaveManager saveManager = new GameSaveManager(3);

        hero.move(5, 3);
        hero.pickUp("Sword");
        System.out.println("State: " + hero);
        saveManager.save(hero.saveGame());
        System.out.println("  [Saved slot 0]");

        hero.move(10, -2);
        hero.takeDamage(30);
        hero.pickUp("Shield");
        System.out.println("State: " + hero);
        saveManager.save(hero.saveGame());
        System.out.println("  [Saved slot 1]");

        hero.takeDamage(80);
        System.out.println("After boss fight: " + hero);

        // Load earlier save
        System.out.println("  [Loading slot 0]");
        hero.loadGame(saveManager.load(0));
        System.out.println("Restored: " + hero);

        // Demonstrate max slots
        System.out.println("\n--- Max Slots Demo (limit=3) ---");
        for (int i = 0; i < 4; i++) {
            hero.move(1, 1);
            saveManager.save(hero.saveGame());
            System.out.println("  Save count: " + saveManager.getSaveCount());
        }
    }
}
