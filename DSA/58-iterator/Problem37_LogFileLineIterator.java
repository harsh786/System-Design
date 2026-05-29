import java.util.*;

public class Problem37_LogFileLineIterator implements Iterator<String> {
    // Simulate reading log file line by line
    String[] lines;
    int idx = 0;
    String filterLevel; // null means no filter

    public Problem37_LogFileLineIterator(String[] logContent, String filterLevel) {
        this.lines = logContent; this.filterLevel = filterLevel; advance();
    }

    void advance() {
        if (filterLevel == null) return;
        while (idx < lines.length && !lines[idx].contains("[" + filterLevel + "]")) idx++;
    }

    public boolean hasNext() { return idx < lines.length; }

    public String next() { String line = lines[idx++]; advance(); return line; }

    public static void main(String[] args) {
        String[] logs = {"[INFO] started", "[ERROR] disk full", "[INFO] request", "[ERROR] timeout", "[DEBUG] trace"};
        Problem37_LogFileLineIterator it = new Problem37_LogFileLineIterator(logs, "ERROR");
        while (it.hasNext()) System.out.println(it.next());
    }
}
