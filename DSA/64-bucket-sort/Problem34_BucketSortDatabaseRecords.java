import java.util.*;
public class Problem34_BucketSortDatabaseRecords {
    static class Record { int id; String name; int age; Record(int id,String n,int a){this.id=id;name=n;age=a;} public String toString(){return "("+id+","+name+","+age+")";} }
    public Record[] sortByAge(Record[] records) {
        List<Record>[] buckets=new List[151]; for(int i=0;i<151;i++) buckets[i]=new ArrayList<>();
        for(Record r:records) buckets[r.age].add(r);
        int idx=0; for(List<Record> b:buckets) for(Record r:b) records[idx++]=r;
        return records;
    }
    public static void main(String[] args){ Record[] r={new Record(1,"Alice",30),new Record(2,"Bob",25),new Record(3,"Carol",30),new Record(4,"Dave",22)}; new Problem34_BucketSortDatabaseRecords().sortByAge(r); System.out.println(Arrays.toString(r)); }
}
