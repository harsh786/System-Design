import java.util.*;

public class Problem16_RandomizedCollection {
    // Same as Problem12 - duplicates allowed
    Map<Integer, TreeSet<Integer>> map = new HashMap<>();
    List<Integer> list = new ArrayList<>();
    Random rand = new Random();

    public boolean insert(int val) {
        map.computeIfAbsent(val, k -> new TreeSet<>()).add(list.size());
        list.add(val);
        return map.get(val).size() == 1;
    }

    public boolean remove(int val) {
        if (!map.containsKey(val) || map.get(val).isEmpty()) return false;
        int idx = map.get(val).first(); map.get(val).remove(idx);
        int last = list.get(list.size()-1);
        if (idx != list.size()-1) {
            list.set(idx, last);
            map.get(last).remove(list.size()-1);
            map.get(last).add(idx);
        }
        list.remove(list.size()-1);
        if (map.get(val).isEmpty()) map.remove(val);
        return true;
    }

    public int getRandom() { return list.get(rand.nextInt(list.size())); }

    public static void main(String[] args) {
        Problem16_RandomizedCollection c = new Problem16_RandomizedCollection();
        c.insert(1); c.insert(1); c.insert(2);
        System.out.println(c.getRandom());
        c.remove(1);
        System.out.println(c.getRandom());
    }
}
