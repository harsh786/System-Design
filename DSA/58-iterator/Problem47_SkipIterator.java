import java.util.*;

public class Problem47_SkipIterator implements Iterator<Integer> {
    Iterator<Integer> source;
    Map<Integer, Integer> skipCount = new HashMap<>();
    Integer nextVal;

    public Problem47_SkipIterator(Iterator<Integer> source) { this.source = source; advance(); }

    void advance() {
        nextVal = null;
        while (source.hasNext()) {
            int val = source.next();
            if (skipCount.getOrDefault(val, 0) > 0) { skipCount.merge(val, -1, Integer::sum); }
            else { nextVal = val; return; }
        }
    }

    public void skip(int val) {
        if (nextVal != null && nextVal == val) advance();
        else skipCount.merge(val, 1, Integer::sum);
    }

    public boolean hasNext() { return nextVal != null; }
    public Integer next() { int val = nextVal; advance(); return val; }

    public static void main(String[] args) {
        Problem47_SkipIterator it = new Problem47_SkipIterator(Arrays.asList(2,3,5,6,5,7,5,6,8,9).iterator());
        System.out.println(it.hasNext()); // true
        System.out.println(it.next());    // 2
        it.skip(5);
        System.out.println(it.next());    // 3
        System.out.println(it.next());    // 6 (5 was skipped)
    }
}
