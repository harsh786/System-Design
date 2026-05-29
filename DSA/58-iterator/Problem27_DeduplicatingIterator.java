import java.util.*;

public class Problem27_DeduplicatingIterator implements Iterator<Integer> {
    Iterator<Integer> source;
    Integer nextVal;
    boolean hasNextVal;

    public Problem27_DeduplicatingIterator(Iterator<Integer> sorted) {
        source = sorted; advance();
    }

    void advance() {
        Integer prev = nextVal;
        hasNextVal = false;
        while (source.hasNext()) {
            nextVal = source.next();
            if (!nextVal.equals(prev)) { hasNextVal = true; return; }
        }
    }

    public boolean hasNext() { return hasNextVal; }
    public Integer next() { Integer val = nextVal; advance(); return val; }

    public static void main(String[] args) {
        Problem27_DeduplicatingIterator it = new Problem27_DeduplicatingIterator(
            Arrays.asList(1,1,2,3,3,3,4,5,5).iterator());
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 2 3 4 5
    }
}
