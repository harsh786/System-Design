import java.util.*;

public class Problem38_RankTransformOfAStream {
    // Rank transform: as numbers arrive in stream, assign rank (1-based by sorted order)
    TreeMap<Integer, Integer> map = new TreeMap<>();
    int size = 0;

    public int addAndRank(int val) {
        map.merge(val, 1, Integer::sum);
        size++;
        int rank = 0;
        for (var e : map.headMap(val).entrySet()) rank += e.getValue();
        return rank + 1; // 1-based rank
    }

    public static void main(String[] args) {
        Problem38_RankTransformOfAStream rt = new Problem38_RankTransformOfAStream();
        System.out.println(rt.addAndRank(5)); // 1
        System.out.println(rt.addAndRank(3)); // 1
        System.out.println(rt.addAndRank(8)); // 3
        System.out.println(rt.addAndRank(4)); // 2
    }
}
