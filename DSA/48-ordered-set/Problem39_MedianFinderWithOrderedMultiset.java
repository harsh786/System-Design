import java.util.*;

public class Problem39_MedianFinderWithOrderedMultiset {
    // LC 295: Find Median from Data Stream using two TreeMaps as multisets
    TreeMap<Integer, Integer> lo = new TreeMap<>(Collections.reverseOrder());
    TreeMap<Integer, Integer> hi = new TreeMap<>();
    int loSize = 0, hiSize = 0;

    public void addNum(int num) {
        lo.merge(num, 1, Integer::sum); loSize++;
        int top = lo.firstKey();
        lo.merge(top, -1, Integer::sum); if (lo.get(top) == 0) lo.remove(top); loSize--;
        hi.merge(top, 1, Integer::sum); hiSize++;
        if (hiSize > loSize) {
            int bot = hi.firstKey();
            hi.merge(bot, -1, Integer::sum); if (hi.get(bot) == 0) hi.remove(bot); hiSize--;
            lo.merge(bot, 1, Integer::sum); loSize++;
        }
    }

    public double findMedian() {
        if (loSize > hiSize) return lo.firstKey();
        return ((long) lo.firstKey() + hi.firstKey()) / 2.0;
    }

    public static void main(String[] args) {
        Problem39_MedianFinderWithOrderedMultiset mf = new Problem39_MedianFinderWithOrderedMultiset();
        mf.addNum(1); mf.addNum(2);
        System.out.println(mf.findMedian()); // 1.5
        mf.addNum(3);
        System.out.println(mf.findMedian()); // 2.0
    }
}
