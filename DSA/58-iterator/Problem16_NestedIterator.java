import java.util.*;

public class Problem16_NestedIterator implements Iterator<Integer> {
    Deque<Iterator<Object>> stack = new ArrayDeque<>();

    @SuppressWarnings("unchecked")
    public Problem16_NestedIterator(List<Object> nested) { stack.push(nested.iterator()); }

    public boolean hasNext() {
        while (!stack.isEmpty()) {
            if (!stack.peek().hasNext()) { stack.pop(); continue; }
            return true;
        }
        return false;
    }

    @SuppressWarnings("unchecked")
    public Integer next() {
        Object obj = stack.peek().next();
        if (obj instanceof Integer) return (Integer) obj;
        stack.push(((List<Object>) obj).iterator());
        return next();
    }

    public static void main(String[] args) {
        List<Object> nested = new ArrayList<>();
        nested.add(Arrays.asList(1, 2));
        nested.add(3);
        nested.add(Arrays.asList(4, Arrays.asList(5, 6)));
        Problem16_NestedIterator it = new Problem16_NestedIterator(nested);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
