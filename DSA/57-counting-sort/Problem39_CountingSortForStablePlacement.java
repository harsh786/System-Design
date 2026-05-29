import java.util.*;

public class Problem39_CountingSortForStablePlacement {
    // Stable sort students by grade preserving original order
    static class Student { String name; int grade;
        Student(String n, int g){name=n;grade=g;}
        public String toString(){return name+"("+grade+")";}
    }

    public static List<Student> stableSort(List<Student> students) {
        List<Student>[] buckets = new List[101];
        for (int i = 0; i <= 100; i++) buckets[i] = new ArrayList<>();
        for (Student s : students) buckets[s.grade].add(s);
        List<Student> result = new ArrayList<>();
        for (List<Student> b : buckets) result.addAll(b);
        return result;
    }

    public static void main(String[] args) {
        List<Student> students = Arrays.asList(
            new Student("Alice",85), new Student("Bob",92),
            new Student("Charlie",85), new Student("Dave",78));
        System.out.println(stableSort(students));
    }
}
