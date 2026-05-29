import java.util.*;

public class Problem04_DataStreamAsDisjointIntervals {
    // 352. Data Stream as Disjoint Intervals.
    
    TreeMap<Integer, int[]> map = new TreeMap<>(); // start -> [start, end]
    
    public void addNum(int val) {
        if (map.containsKey(val)) return;
        Integer lo = map.lowerKey(val), hi = map.higherKey(val);
        boolean mergeLeft = lo != null && map.get(lo)[1] >= val - 1;
        boolean mergeRight = hi != null && hi == val + 1;
        
        if (mergeLeft && mergeRight) {
            map.get(lo)[1] = map.get(hi)[1];
            map.remove(hi);
        } else if (mergeLeft) {
            map.get(lo)[1] = Math.max(map.get(lo)[1], val);
        } else if (mergeRight) {
            map.put(val, new int[]{val, map.get(hi)[1]});
            map.remove(hi);
        } else {
            map.put(val, new int[]{val, val});
        }
    }
    
    public int[][] getIntervals() {
        return map.values().toArray(new int[0][]);
    }
    
    public static void main(String[] args) {
        Problem04_DataStreamAsDisjointIntervals sol = new Problem04_DataStreamAsDisjointIntervals();
        sol.addNum(1); sol.addNum(3); sol.addNum(7); sol.addNum(2); sol.addNum(6);
        for (int[] interval : sol.getIntervals())
            System.out.print(Arrays.toString(interval) + " ");
        // [1,3] [6,7]
        System.out.println();
    }
}
