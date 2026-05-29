import java.util.*;

public class Problem23_LookaheadIterator<T> implements Iterator<T> {
    Iterator<T> source;
    Deque<T> buffer = new ArrayDeque<>();
    int lookahead;

    public Problem23_LookaheadIterator(Iterator<T> source, int lookahead) {
        this.source = source; this.lookahead = lookahead;
        for (int i = 0; i < lookahead && source.hasNext(); i++) buffer.offer(source.next());
    }

    public T peek(int ahead) { // 0-indexed lookahead
        Iterator<T> it = buffer.iterator();
        for (int i = 0; i < ahead; i++) { if (!it.hasNext()) return null; it.next(); }
        return it.hasNext() ? it.next() : null;
    }

    public boolean hasNext() { return !buffer.isEmpty(); }
    public T next() { T val = buffer.poll(); if (source.hasNext()) buffer.offer(source.next()); return val; }

    public static void main(String[] args) {
        Problem23_LookaheadIterator<Integer> it = new Problem23_LookaheadIterator<>(Arrays.asList(1,2,3,4,5).iterator(), 3);
        System.out.println("Peek 0: " + it.peek(0)); // 1
        System.out.println("Peek 2: " + it.peek(2)); // 3
        System.out.println("Next: " + it.next()); // 1
        System.out.println("Peek 0: " + it.peek(0)); // 2
    }
}
