import java.util.*;

// =============================================================================
// EXAMPLE 1: Data Mining Framework
// =============================================================================

abstract class DataMiner {
    // Template Method - defines the skeleton algorithm
    public final void mine(String path) {
        openFile(path);
        String rawData = extractData();
        List<String> data = parseData(rawData);
        if (shouldAnalyze()) { // Hook method
            analyzeData(data);
        }
        generateReport(data);
        beforeClose(); // Hook method
        closeFile();
    }

    abstract void openFile(String path);
    abstract String extractData();
    abstract List<String> parseData(String rawData);
    abstract void closeFile();

    // Common implementation (can be overridden)
    void analyzeData(List<String> data) {
        System.out.println("  [Base] Analyzing " + data.size() + " records...");
    }

    void generateReport(List<String> data) {
        System.out.println("  [Base] Generating report with " + data.size() + " entries.");
    }

    // Hook methods - optional override points
    boolean shouldAnalyze() { return true; }
    void beforeClose() { /* do nothing by default */ }
}

class CSVDataMiner extends DataMiner {
    void openFile(String path) { System.out.println("  [CSV] Opening CSV file: " + path); }
    String extractData() { System.out.println("  [CSV] Reading rows..."); return "name,age\nAlice,30\nBob,25"; }
    List<String> parseData(String rawData) {
        System.out.println("  [CSV] Parsing comma-separated values...");
        return Arrays.asList(rawData.split("\n"));
    }
    void closeFile() { System.out.println("  [CSV] Closing CSV file."); }
}

class JSONDataMiner extends DataMiner {
    void openFile(String path) { System.out.println("  [JSON] Opening JSON file: " + path); }
    String extractData() { System.out.println("  [JSON] Reading JSON content..."); return "{\"users\":[{\"name\":\"Alice\"},{\"name\":\"Bob\"}]}"; }
    List<String> parseData(String rawData) {
        System.out.println("  [JSON] Parsing JSON objects...");
        return Arrays.asList("Alice", "Bob");
    }
    void closeFile() { System.out.println("  [JSON] Closing JSON file."); }

    @Override
    void beforeClose() { System.out.println("  [JSON] Validating JSON structure before close..."); }
}

class XMLDataMiner extends DataMiner {
    void openFile(String path) { System.out.println("  [XML] Opening XML file: " + path); }
    String extractData() { System.out.println("  [XML] Reading XML nodes..."); return "<users><user>Alice</user><user>Bob</user></users>"; }
    List<String> parseData(String rawData) {
        System.out.println("  [XML] Parsing XML elements...");
        return Arrays.asList("Alice", "Bob");
    }
    void closeFile() { System.out.println("  [XML] Closing XML file."); }

    @Override
    boolean shouldAnalyze() { return false; } // Skip analysis for XML
}

class DatabaseDataMiner extends DataMiner {
    void openFile(String path) { System.out.println("  [DB] Connecting to database: " + path); }
    String extractData() { System.out.println("  [DB] Executing SQL query..."); return "ROW1;ROW2;ROW3"; }
    List<String> parseData(String rawData) {
        System.out.println("  [DB] Parsing result set...");
        return Arrays.asList(rawData.split(";"));
    }
    void closeFile() { System.out.println("  [DB] Closing database connection."); }

    @Override
    void analyzeData(List<String> data) {
        System.out.println("  [DB] Running DB-specific statistical analysis on " + data.size() + " rows...");
    }
}

// =============================================================================
// EXAMPLE 2: Game Framework
// =============================================================================

abstract class Game {
    // Template Method
    public final void play() {
        initialize();
        startPlay();
        if (hasHalftime()) { halftime(); }
        endPlay();
    }

    abstract void initialize();
    abstract void startPlay();
    abstract void endPlay();

    // Hook methods
    boolean hasHalftime() { return false; }
    void halftime() { System.out.println("  [Game] Halftime break!"); }
}

class Cricket extends Game {
    void initialize() { System.out.println("  [Cricket] Gathering 11 players, setting up pitch."); }
    void startPlay() { System.out.println("  [Cricket] First innings begins. Batsman takes strike!"); }
    void endPlay() { System.out.println("  [Cricket] Match over. Man of the match announced."); }

    @Override
    boolean hasHalftime() { return true; }
    @Override
    void halftime() { System.out.println("  [Cricket] Innings break - teams switch."); }
}

class Football extends Game {
    void initialize() { System.out.println("  [Football] 11 players on each side, coin toss done."); }
    void startPlay() { System.out.println("  [Football] Kickoff! Ball is in play."); }
    void endPlay() { System.out.println("  [Football] Full time whistle. Final score announced."); }

    @Override
    boolean hasHalftime() { return true; }
    @Override
    void halftime() { System.out.println("  [Football] Halftime - 15 minute break."); }
}

// =============================================================================
// EXAMPLE 3: Beverage Preparation
// =============================================================================

abstract class Beverage {
    // Template Method
    public final void prepare() {
        boilWater();
        brew();
        pourInCup();
        if (wantsCondiments()) {
            addCondiments();
        }
        System.out.println("  Ready to serve!\n");
    }

    void boilWater() { System.out.println("  Boiling water..."); }
    void pourInCup() { System.out.println("  Pouring into cup..."); }

    abstract void brew();
    abstract void addCondiments();

    // Hook
    boolean wantsCondiments() { return true; }
}

class Tea extends Beverage {
    void brew() { System.out.println("  Steeping tea leaves for 3 minutes..."); }
    void addCondiments() { System.out.println("  Adding lemon and honey..."); }
}

class Coffee extends Beverage {
    void brew() { System.out.println("  Dripping coffee through filter..."); }
    void addCondiments() { System.out.println("  Adding sugar and milk..."); }
}

class BlackCoffee extends Beverage {
    void brew() { System.out.println("  Brewing strong espresso..."); }
    void addCondiments() { /* won't be called */ }

    @Override
    boolean wantsCondiments() { return false; }
}

// =============================================================================
// MAIN
// =============================================================================

public class TemplateMethodPattern {
    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════╗");
        System.out.println("║       TEMPLATE METHOD DESIGN PATTERN DEMO           ║");
        System.out.println("╚══════════════════════════════════════════════════════╝\n");

        // Example 1: Data Mining
        System.out.println("━━━ EXAMPLE 1: Data Mining Framework ━━━\n");
        DataMiner[] miners = { new CSVDataMiner(), new JSONDataMiner(), new XMLDataMiner(), new DatabaseDataMiner() };
        String[] paths = { "data.csv", "data.json", "data.xml", "jdbc:mysql://localhost/db" };
        for (int i = 0; i < miners.length; i++) {
            System.out.println("▶ " + miners[i].getClass().getSimpleName() + ":");
            miners[i].mine(paths[i]);
            System.out.println();
        }

        // Example 2: Game Framework
        System.out.println("━━━ EXAMPLE 2: Game Framework ━━━\n");
        System.out.println("▶ Cricket:");
        new Cricket().play();
        System.out.println("\n▶ Football:");
        new Football().play();
        System.out.println();

        // Example 3: Beverage
        System.out.println("━━━ EXAMPLE 3: Beverage Preparation ━━━\n");
        System.out.println("▶ Tea:");
        new Tea().prepare();
        System.out.println("▶ Coffee:");
        new Coffee().prepare();
        System.out.println("▶ Black Coffee (no condiments - hook override):");
        new BlackCoffee().prepare();
    }
}
