import java.util.*;

public class Problem28_CountingSortForLogSeverity {
    // Sort logs by severity: DEBUG=0, INFO=1, WARN=2, ERROR=3, FATAL=4
    static class LogEntry { int severity; String msg;
        LogEntry(int s, String m){severity=s;msg=m;}
        public String toString(){return severity+":"+msg;}
    }

    public static List<LogEntry> sortBySeverity(List<LogEntry> logs) {
        List<LogEntry>[] buckets = new List[5];
        for (int i = 0; i < 5; i++) buckets[i] = new ArrayList<>();
        for (LogEntry l : logs) buckets[l.severity].add(l);
        List<LogEntry> result = new ArrayList<>();
        for (List<LogEntry> b : buckets) result.addAll(b);
        return result;
    }

    public static void main(String[] args) {
        List<LogEntry> logs = Arrays.asList(new LogEntry(3,"err1"), new LogEntry(1,"info1"),
            new LogEntry(4,"fatal1"), new LogEntry(0,"debug1"));
        System.out.println(sortBySeverity(logs));
    }
}
