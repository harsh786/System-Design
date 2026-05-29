import java.util.*;

public class Problem17_OnlineRankQuery {
    // Online rank query: maintain a sorted structure, query rank of element
    TreeMap<Integer, Integer> map;
    int totalCount;

    public Problem17_OnlineRankQuery() {
        map = new TreeMap<>();
        totalCount = 0;
    }

    public void add(int val) {
        map.merge(val, 1, Integer::sum);
        totalCount++;
    }

    // Returns number of elements strictly less than val
    public int rank(int val) {
        int count = 0;
        for (Map.Entry<Integer, Integer> e : map.headMap(val).entrySet()) {
            count += e.getValue();
        }
        return count;
    }

    public static void main(String[] args) {
        Problem17_OnlineRankQuery q = new Problem17_OnlineRankQuery();
        q.add(5); q.add(3); q.add(8); q.add(3);
        System.out.println(q.rank(5)); // 2 (two 3's are less)
        System.out.println(q.rank(3)); // 0
        System.out.println(q.rank(9)); // 4
    }
}
