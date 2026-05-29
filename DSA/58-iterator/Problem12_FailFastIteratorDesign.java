import java.util.*;

public class Problem12_FailFastIteratorDesign {
    static class FailFastList<T> {
        List<T> data = new ArrayList<>();
        int modCount = 0;

        void add(T item) { data.add(item); modCount++; }
        void remove(int idx) { data.remove(idx); modCount++; }

        Iterator<T> iterator() {
            return new Iterator<T>() {
                int expectedMod = modCount, idx = 0;
                public boolean hasNext() { checkMod(); return idx < data.size(); }
                public T next() { checkMod(); return data.get(idx++); }
                void checkMod() { if (modCount != expectedMod) throw new ConcurrentModificationException(); }
            };
        }
    }

    public static void main(String[] args) {
        FailFastList<Integer> list = new FailFastList<>();
        list.add(1); list.add(2); list.add(3);
        Iterator<Integer> it = list.iterator();
        System.out.println(it.next()); // 1
        list.add(4); // modify
        try { it.next(); } catch (ConcurrentModificationException e) { System.out.println("ConcurrentModificationException caught!"); }
    }
}
