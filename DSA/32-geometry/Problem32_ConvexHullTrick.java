import java.util.*;

public class Problem32_ConvexHullTrick {
    // Maintains a set of lines y = mx + b, answers min query for given x
    static List<long[]> lines = new ArrayList<>(); // {m, b}
    static boolean bad(long[] l1, long[] l2, long[] l3) {
        return (double)(l3[1]-l1[1])*(l1[0]-l2[0]) <= (double)(l2[1]-l1[1])*(l1[0]-l3[0]);
    }
    static void addLine(long m, long b) {
        long[] line = {m, b};
        while (lines.size() >= 2 && bad(lines.get(lines.size()-2), lines.get(lines.size()-1), line))
            lines.remove(lines.size()-1);
        lines.add(line);
    }
    static long query(long x) {
        int lo = 0, hi = lines.size() - 1;
        while (lo < hi) {
            int mid = (lo+hi)/2;
            if (lines.get(mid)[0]*x + lines.get(mid)[1] > lines.get(mid+1)[0]*x + lines.get(mid+1)[1]) lo = mid+1;
            else hi = mid;
        }
        return lines.get(lo)[0]*x + lines.get(lo)[1];
    }
    public static void main(String[] args) {
        lines.clear();
        addLine(1, 0); addLine(-1, 4); addLine(2, -3);
        System.out.println(query(1)); // min at x=1
        System.out.println(query(3));
    }
}
