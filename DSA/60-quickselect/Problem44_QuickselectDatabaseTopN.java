import java.util.*;

public class Problem44_QuickselectDatabaseTopN {
    /* Simulate database Top-N query using quickselect */
    static class Record { int id; double score;
        Record(int id, double score) { this.id = id; this.score = score; }
        public String toString() { return "(" + id + "," + score + ")"; }
    }

    public List<Record> topN(Record[] records, int n) {
        quickselect(records, 0, records.length - 1, records.length - n);
        List<Record> result = new ArrayList<>();
        for (int i = records.length - n; i < records.length; i++) result.add(records[i]);
        result.sort((a, b) -> Double.compare(b.score, a.score));
        return result;
    }

    private void quickselect(Record[] a, int lo, int hi, int k) {
        if (lo >= hi) return;
        int pi = partition(a, lo, hi);
        if (pi == k) return;
        else if (pi < k) quickselect(a, pi + 1, hi, k);
        else quickselect(a, lo, pi - 1, k);
    }

    private int partition(Record[] a, int lo, int hi) {
        double pivot = a[hi].score; int s = lo;
        for (int i = lo; i < hi; i++) if (a[i].score < pivot) { Record t = a[s]; a[s] = a[i]; a[i] = t; s++; }
        Record t = a[s]; a[s] = a[hi]; a[hi] = t;
        return s;
    }

    public static void main(String[] args) {
        Problem44_QuickselectDatabaseTopN sol = new Problem44_QuickselectDatabaseTopN();
        Record[] records = {new Record(1,3.5), new Record(2,9.1), new Record(3,7.2), new Record(4,1.0), new Record(5,8.8)};
        System.out.println(sol.topN(records, 3));
    }
}
