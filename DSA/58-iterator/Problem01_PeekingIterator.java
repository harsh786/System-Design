import java.util.*;

public class Problem01_PeekingIterator implements Iterator<Integer> {
    Iterator<Integer> iter;
    Integer peeked;
    boolean hasPeeked;

    public Problem01_PeekingIterator(Iterator<Integer> iterator) {
        iter = iterator; hasPeeked = false;
    }

    public Integer peek() {
        if (!hasPeeked) { peeked = iter.next(); hasPeeked = true; }
        return peeked;
    }

    public Integer next() {
        if (hasPeeked) { hasPeeked = false; return peeked; }
        return iter.next();
    }

    public boolean hasNext() { return hasPeeked || iter.hasNext(); }

    public static void main(String[] args) {
        Problem01_PeekingIterator pi = new Problem01_PeekingIterator(Arrays.asList(1,2,3).iterator());
        System.out.println(pi.peek());    // 1
        System.out.println(pi.next());    // 1
        System.out.println(pi.next());    // 2
        System.out.println(pi.hasNext()); // true
        System.out.println(pi.next());    // 3
        System.out.println(pi.hasNext()); // false
    }
}
