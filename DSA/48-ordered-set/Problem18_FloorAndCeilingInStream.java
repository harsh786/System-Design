import java.util.*;

public class Problem18_FloorAndCeilingInStream {
    // Find floor and ceiling of a value in a dynamic stream
    TreeSet<Integer> set;

    public Problem18_FloorAndCeilingInStream() {
        set = new TreeSet<>();
    }

    public void add(int val) { set.add(val); }
    public Integer floor(int val) { return set.floor(val); }
    public Integer ceiling(int val) { return set.ceiling(val); }

    public static void main(String[] args) {
        Problem18_FloorAndCeilingInStream s = new Problem18_FloorAndCeilingInStream();
        s.add(2); s.add(8); s.add(5); s.add(10);
        System.out.println(s.floor(7));   // 5
        System.out.println(s.ceiling(7)); // 8
        System.out.println(s.floor(1));   // null
    }
}
