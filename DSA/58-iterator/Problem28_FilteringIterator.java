import java.util.*;
import java.util.function.Predicate;

public class Problem28_FilteringIterator<T> implements Iterator<T> {
    Iterator<T> source;
    Predicate<T> predicate;
    T nextVal; boolean hasNextVal;

    public Problem28_FilteringIterator(Iterator<T> source, Predicate<T> predicate) {
        this.source = source; this.predicate = predicate; advance();
    }

    void advance() {
        hasNextVal = false;
        while (source.hasNext()) {
            T val = source.next();
            if (predicate.test(val)) { nextVal = val; hasNextVal = true; return; }
        }
    }

    public boolean hasNext() { return hasNextVal; }
    public T next() { T val = nextVal; advance(); return val; }

    public static void main(String[] args) {
        Problem28_FilteringIterator<Integer> it = new Problem28_FilteringIterator<>(
            Arrays.asList(1,2,3,4,5,6,7,8,9,10).iterator(), n -> n % 2 == 0);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 2 4 6 8 10
    }
}
