import java.util.*;

public class Problem48_PeekableStreamIterator<T> implements Iterator<T> {
    Iterator<T> source;
    T peeked; boolean hasPeeked;

    public Problem48_PeekableStreamIterator(Iterator<T> source) { this.source = source; }

    public T peek() { if (!hasPeeked) { peeked = source.next(); hasPeeked = true; } return peeked; }
    public boolean hasNext() { return hasPeeked || source.hasNext(); }
    public T next() { if (hasPeeked) { hasPeeked = false; return peeked; } return source.next(); }

    // Peek and consume while condition holds
    public List<T> takeWhile(java.util.function.Predicate<T> pred) {
        List<T> result = new ArrayList<>();
        while (hasNext() && pred.test(peek())) result.add(next());
        return result;
    }

    public static void main(String[] args) {
        Problem48_PeekableStreamIterator<Integer> it = new Problem48_PeekableStreamIterator<>(
            Arrays.asList(1,2,3,4,5,6,7,8,9).iterator());
        System.out.println("Take while < 5: " + it.takeWhile(n -> n < 5));
        System.out.println("Next: " + it.next()); // 5
    }
}
