import java.util.*;

public class Problem12_RandomizedSetWithDuplicates {
    Map<Integer, Set<Integer>> map;
    List<Integer> list;
    Random rand;

    public Problem12_RandomizedSetWithDuplicates() {
        map = new HashMap<>(); list = new ArrayList<>(); rand = new Random();
    }

    public boolean insert(int val) {
        map.computeIfAbsent(val, k -> new LinkedHashSet<>()).add(list.size());
        list.add(val);
        return map.get(val).size() == 1;
    }

    public boolean remove(int val) {
        if (!map.containsKey(val) || map.get(val).isEmpty()) return false;
        int idx = map.get(val).iterator().next();
        map.get(val).remove(idx);
        int last = list.get(list.size() - 1);
        list.set(idx, last);
        map.get(last).add(idx);
        map.get(last).remove(list.size() - 1);
        list.remove(list.size() - 1);
        return true;
    }

    public int getRandom() { return list.get(rand.nextInt(list.size())); }

    public static void main(String[] args) {
        Problem12_RandomizedSetWithDuplicates s = new Problem12_RandomizedSetWithDuplicates();
        s.insert(1); s.insert(1); s.insert(2);
        System.out.println(s.getRandom());
        s.remove(1);
        System.out.println(s.getRandom());
    }
}
