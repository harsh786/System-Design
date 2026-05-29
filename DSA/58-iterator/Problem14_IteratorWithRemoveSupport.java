import java.util.*;

public class Problem14_IteratorWithRemoveSupport {
    static class RemovableIterator<T> implements Iterator<T> {
        List<T> list; int idx = 0; boolean canRemove = false;
        RemovableIterator(List<T> list) { this.list = list; }
        public boolean hasNext() { return idx < list.size(); }
        public T next() { canRemove = true; return list.get(idx++); }
        public void remove() {
            if (!canRemove) throw new IllegalStateException();
            list.remove(--idx); canRemove = false;
        }
    }

    public static void main(String[] args) {
        List<Integer> list = new ArrayList<>(Arrays.asList(1,2,3,4,5));
        RemovableIterator<Integer> it = new RemovableIterator<>(list);
        while (it.hasNext()) { if (it.next() % 2 == 0) it.remove(); }
        System.out.println(list); // [1,3,5]
    }
}
