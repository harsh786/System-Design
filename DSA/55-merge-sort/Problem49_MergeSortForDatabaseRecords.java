import java.util.*;

public class Problem49_MergeSortForDatabaseRecords {
    static class Record implements Comparable<Record> {
        int id; String name; long timestamp;
        Record(int id, String name, long ts) { this.id=id; this.name=name; timestamp=ts; }
        public int compareTo(Record o) { return Long.compare(timestamp, o.timestamp); }
        public String toString() { return id+":"+name+"@"+timestamp; }
    }
    
    static Record[] mergeSort(Record[] records) {
        if (records.length <= 1) return records;
        int mid = records.length / 2;
        Record[] left = mergeSort(Arrays.copyOfRange(records, 0, mid));
        Record[] right = mergeSort(Arrays.copyOfRange(records, mid, records.length));
        Record[] result = new Record[records.length]; int i=0,j=0,k=0;
        while(i<left.length&&j<right.length)result[k++]=left[i].compareTo(right[j])<=0?left[i++]:right[j++];
        while(i<left.length)result[k++]=left[i++];while(j<right.length)result[k++]=right[j++];
        return result;
    }
    
    public static void main(String[] args) {
        Record[] records = {new Record(1,"alice",300),new Record(2,"bob",100),new Record(3,"charlie",200)};
        records = mergeSort(records);
        System.out.println(Arrays.toString(records));
    }
}
