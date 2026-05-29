import java.util.*;

public class Problem05_DataStreamAsDisjointIntervals {
    // LC 352: Given a stream of integers, find disjoint intervals
    TreeMap<Integer, int[]> tree;

    public Problem05_DataStreamAsDisjointIntervals() {
        tree = new TreeMap<>();
    }

    public void addNum(int val) {
        if (tree.containsKey(val)) return;
        Integer lo = tree.lowerKey(val);
        Integer hi = tree.higherKey(val);
        if (lo != null && tree.get(lo)[1] + 1 == val && hi != null && hi == val + 1) {
            tree.get(lo)[1] = tree.get(hi)[1];
            tree.remove(hi);
        } else if (lo != null && tree.get(lo)[1] + 1 >= val) {
            tree.get(lo)[1] = Math.max(tree.get(lo)[1], val);
        } else if (hi != null && hi == val + 1) {
            tree.put(val, new int[]{val, tree.get(hi)[1]});
            tree.remove(hi);
        } else {
            tree.put(val, new int[]{val, val});
        }
    }

    public int[][] getIntervals() {
        return tree.values().toArray(new int[0][]);
    }

    public static void main(String[] args) {
        Problem05_DataStreamAsDisjointIntervals ds = new Problem05_DataStreamAsDisjointIntervals();
        ds.addNum(1); ds.addNum(3); ds.addNum(7); ds.addNum(2); ds.addNum(6);
        for (int[] iv : ds.getIntervals()) System.out.println(Arrays.toString(iv));
        // [1,3] [6,7]
    }
}
